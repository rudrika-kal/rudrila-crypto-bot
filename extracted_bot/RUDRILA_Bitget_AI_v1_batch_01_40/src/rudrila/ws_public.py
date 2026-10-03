from __future__ import annotations
import asyncio,json,time
import websockets
from .market_state import SymbolState

def _f(d, key, old=None):
    x=d.get(key)
    try: return float(x) if x not in (None,"") else old
    except (TypeError,ValueError): return old

def _normalize_kline_row(row):
    """Normalize Bitget UTA V3 kline objects to REST-style arrays.

    UTA V3 WebSocket kline pushes use objects like:
    {start, open, high, low, close, volume, turnover}.
    REST history/candle responses use arrays.  Runtime code consumes one
    canonical array shape for both paths.
    """
    if isinstance(row, dict):
        start = row.get('start')
        o = row.get('open')
        h = row.get('high')
        l = row.get('low')
        c = row.get('close')
        if None in (start, o, h, l, c):
            return None
        return [
            str(start), str(o), str(h), str(l), str(c),
            str(row.get('volume') or '0'),
            str(row.get('turnover') or '0'),
        ]
    if isinstance(row, (list, tuple)) and len(row) >= 5:
        out=list(row)
        while len(out) < 7:
            out.append('0')
        return out
    return None

class BitgetPublicDemoWS:
    def __init__(self,settings,symbols=('BTCUSDT','ETHUSDT')):
        self.settings=settings
        self.symbols=tuple(symbols)
        self.states={s:SymbolState(s) for s in self.symbols}
        self._stop=asyncio.Event()

    def subscriptions(self):
        args=[]
        for s in self.symbols:
            args += [
              {'instType':'usdt-futures','topic':'ticker','symbol':s},
              {'instType':'usdt-futures','topic':'publicTrade','symbol':s},
              {'instType':'usdt-futures','topic':'books5','symbol':s},
              {'instType':'usdt-futures','topic':'kline','symbol':s,'interval':'1m'},
              {'instType':'usdt-futures','topic':'kline','symbol':s,'interval':'5m'},
              {'instType':'usdt-futures','topic':'kline','symbol':s,'interval':'15m'}]
        return args

    async def heartbeat(self,ws):
        while not self._stop.is_set():
            await asyncio.sleep(30)
            await ws.send('ping')

    def handle(self,msg):
        arg=msg.get('arg') or {}
        sym=arg.get('symbol')
        topic=arg.get('topic')
        if sym not in self.states: return
        st=self.states[sym]
        ts=int(msg.get('ts') or time.time()*1000)
        data=msg.get('data') or []
        if topic=='ticker' and data:
            d=data[0]
            st.last_price=_f(d,'lastPrice',st.last_price)
            st.bid=_f(d,'bid1Price',st.bid)
            st.ask=_f(d,'ask1Price',st.ask)
            st.mark_price=_f(d,'markPrice',st.mark_price)
            st.index_price=_f(d,'indexPrice',st.index_price)
            st.funding_rate=_f(d,'fundingRate',st.funding_rate)
            st.open_interest=_f(d,'openInterest',st.open_interest)
            st.volume24h=_f(d,'volume24h',st.volume24h)
            nft=d.get('nextFundingTime')
            try: st.next_funding_time=int(nft) if nft not in (None,'') else st.next_funding_time
            except (TypeError,ValueError): pass
            st.touch(ts)
        elif topic=='publicTrade':
            for d in data: st.trades.append(d)
            st.touch(ts)
        elif topic=='books5' and data:
            st.books5=data[0]
            # Use live top-of-book as authoritative execution spread.
            # Ticker bid/ask can momentarily lag during fast markets.
            try:
                bids=st.books5.get('b') or st.books5.get('bids') or []
                asks=st.books5.get('a') or st.books5.get('asks') or []
                best_bid=float(bids[0][0]) if bids else None
                best_ask=float(asks[0][0]) if asks else None
                if best_bid and best_ask and best_bid>0 and best_ask>=best_bid:
                    st.bid=best_bid
                    st.ask=best_ask
            except (TypeError,ValueError,IndexError,KeyError):
                pass
            st.touch(ts)
        elif topic=='kline':
            interval=arg.get('interval')
            for raw_row in data:
                row=_normalize_kline_row(raw_row)
                if not row:
                    continue
                # Bitget can update the open candle once per second. Replace
                # the latest copy instead of filling the deque with duplicates.
                q=st.candles[interval]
                if q and str(q[-1][0]) == str(row[0]):
                    q[-1]=row
                else:
                    q.append(row)
            st.touch(ts)

    async def run_once(self,seconds=20):
        self._stop=asyncio.Event()
        async with websockets.connect(self.settings.public_ws_demo,ping_interval=None,close_timeout=5) as ws:
            await ws.send(json.dumps({'op':'subscribe','args':self.subscriptions()}))
            hb=asyncio.create_task(self.heartbeat(ws))
            end=time.monotonic()+seconds
            try:
                while time.monotonic()<end:
                    raw=await asyncio.wait_for(ws.recv(),timeout=35)
                    if raw=='pong': continue
                    msg=json.loads(raw)
                    if msg.get('event')=='error':
                        raise RuntimeError(f'Bitget WS error: {msg}')
                    self.handle(msg)
            finally:
                self._stop.set()
                hb.cancel()
        return self.states
