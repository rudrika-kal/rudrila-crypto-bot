from __future__ import annotations
import json, urllib.parse, urllib.request, urllib.error
from decimal import Decimal, ROUND_DOWN
from .settings import BitgetSettings
from .bitget_auth import SignedRequest

class BitgetREST:
    def __init__(self, settings: BitgetSettings, timeout: int = 12):
        self.s=settings; self.timeout=timeout

    @staticmethod
    def _clean_api_error(raw: str):
        try:
            out=json.loads(raw or '{}')
        except Exception:
            out={}
        code=str(out.get('code') or 'HTTP_ERROR')
        msg=str(out.get('msg') or out.get('message') or 'Bad Request').replace('\n',' ')[:180]
        return code,msg

    def _request(self, method:str, path:str, *, query:dict|None=None, body:dict|None=None, private=False, paptrading=True):
        query=query or None
        qs=('?'+urllib.parse.urlencode(query)) if query else ''
        raw=json.dumps(body,separators=(',',':')) if body is not None else ''
        headers={'Content-Type':'application/json','User-Agent':'RUDRILA-Bitget-AI/1.1.10b'}
        if private:
            signed=SignedRequest(method,path,query=query,body=raw).headers(self.s)
            if not paptrading:
                signed.pop('paptrading',None)
            headers.update(signed)
        url=self.s.rest_base+path+qs
        data=raw.encode() if body is not None else None
        req=urllib.request.Request(url,data=data,headers=headers,method=method.upper())
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r:
                text=r.read().decode()
        except urllib.error.HTTPError as exc:
            try:
                err=exc.read().decode(errors='replace')
            except Exception:
                err=''
            code,msg=self._clean_api_error(err)
            raise RuntimeError(f'Bitget HTTP {exc.code} path={path} code={code} msg={msg}') from None
        out=json.loads(text)
        if str(out.get('code')) not in ('00000','0'):
            code=str(out.get('code') or 'API_ERROR')
            msg=str(out.get('msg') or out.get('message') or 'request rejected').replace('\n',' ')[:180]
            raise RuntimeError(f'Bitget API path={path} code={code} msg={msg}')
        return out

    def server_time(self):
        return self._request('GET','/api/v2/public/time')
    def instruments(self,symbol:str|None=None):
        q={'category':'USDT-FUTURES'}
        if symbol: q['symbol']=symbol
        return self._request('GET','/api/v3/market/instruments',query=q)
    def candles(self,symbol:str,interval='1m',limit=1000,start_ms=None,end_ms=None,history=False):
        path='/api/v3/market/history-candles' if history else '/api/v3/market/candles'
        if history: limit=min(int(limit),100)
        else: limit=min(int(limit),1000)
        q={'category':'USDT-FUTURES','symbol':symbol,'interval':interval,'limit':str(limit)}
        if start_ms is not None: q['startTime']=str(start_ms)
        if end_ms is not None: q['endTime']=str(end_ms)
        return self._request('GET',path,query=q)
    def orderbook(self,symbol:str,limit=5):
        return self._request('GET','/api/v3/market/orderbook',query={'category':'USDT-FUTURES','symbol':symbol,'limit':str(limit)})
    def recent_fills(self,symbol:str,limit=100):
        return self._request('GET','/api/v3/market/fills',query={'category':'USDT-FUTURES','symbol':symbol,'limit':str(limit)})

    def account_info(self): return self._request('GET','/api/v3/account/info',private=True)
    def account_settings(self): return self._request('GET','/api/v3/account/settings',private=True)
    def account_assets(self): return self._request('GET','/api/v3/account/assets',private=True)

    @staticmethod
    def _base_symbol(symbol:str)->str:
        s=str(symbol or '').upper()
        if s.startswith('SBTC') and 'SUSDT' in s: return 'BTCUSDT'
        if s.startswith('SETH') and 'SUSDT' in s: return 'ETHUSDT'
        if s.endswith('_SUMCBL'):
            s=s[:-7]
        return s

    @staticmethod
    def _synthetic_symbol(symbol:str)->str:
        s=BitgetREST._base_symbol(symbol)
        return {'BTCUSDT':'SBTCSUSDT','ETHUSDT':'SETHSUSDT'}.get(s,s)

    def _classic_variants(self, symbol:str, margin_coin:str|None=None):
        base=self._base_symbol(symbol)
        synth=self._synthetic_symbol(symbol)
        original=str(symbol or '').upper()
        coin=str(margin_coin or 'USDT').upper()
        candidates=[
            (base,'USDT'),
            (synth,'SUSDT'),
            (original,coin),
        ]
        out=[]
        seen=set()
        for sym,mc in candidates:
            k=(sym,mc)
            if sym and k not in seen:
                seen.add(k); out.append(k)
        return out

    def classic_accounts(self, product_type='USDT-FUTURES'):
        return self._request('GET','/api/v2/mix/account/accounts',query={'productType':product_type},private=True)

    def classic_positions(self, product_type='USDT-FUTURES', margin_coin=None):
        q={'productType':product_type}
        if margin_coin: q['marginCoin']=margin_coin
        return self._request('GET','/api/v2/mix/position/all-position',query=q,private=True)

    def classic_single_account(self, symbol:str, margin_coin='USDT', product_type='USDT-FUTURES'):
        errs=[]
        for sym,mc in self._classic_variants(symbol,margin_coin):
            try:
                return self._request('GET','/api/v2/mix/account/account',
                    query={'symbol':sym,'productType':product_type,'marginCoin':mc},
                    private=True,paptrading=True)
            except Exception as exc:
                errs.append(str(exc))
        raise RuntimeError('classic_single_account failed | '+' | '.join(errs[-3:]))

    def classic_set_leverage(self, symbol:str, leverage='2', margin_coin='USDT', product_type='USDT-FUTURES', **kwargs):
        # Runtime calls (symbol, leverage, marginCoin). Current Bitget Classic v2
        # expects normal BTCUSDT/ETHUSDT + USDT. Keep synthetic SUSDT fallback
        # only for older mobile Demo account shapes.
        errs=[]
        for sym,mc in self._classic_variants(symbol,margin_coin):
            body={
                'symbol':sym,
                'productType':product_type,
                'marginCoin':mc,
                'leverage':str(leverage),
            }
            try:
                return self._request('POST','/api/v2/mix/account/set-leverage',
                    body=body,private=True,paptrading=True)
            except Exception as exc:
                errs.append(str(exc))
        raise RuntimeError('classic_set_leverage failed | '+' | '.join(errs[-3:]))

    def classic_place_order(self, body:dict):
        original=dict(body or {})
        errs=[]
        symbol=str(original.get('symbol') or '')
        margin=str(original.get('marginCoin') or 'USDT')
        for sym,mc in self._classic_variants(symbol,margin):
            candidate=dict(original)
            candidate['symbol']=sym
            candidate['productType']='USDT-FUTURES'
            candidate['marginCoin']=mc
            try:
                return self._request('POST','/api/v2/mix/order/place-order',
                    body=candidate,private=True,paptrading=True)
            except Exception as exc:
                errs.append(str(exc))
        raise RuntimeError('classic_place_order failed | '+' | '.join(errs[-3:]))

    # Legacy simulated-coin Demo endpoints remain hard-whitelisted and separate.
    @staticmethod
    def _assert_legacy_sim_symbol(symbol:str):
        allowed={'SBTCSUSDT_SUMCBL','SETHSUSDT_SUMCBL'}
        if str(symbol).upper() not in allowed:
            raise RuntimeError('legacy simulated backend rejects non-demo symbol')
    def legacy_sim_contracts(self):
        return self._request('GET','/api/mix/v1/market/contracts',query={'productType':'sumcbl'},private=False,paptrading=False)
    def legacy_sim_account(self, symbol='SBTCSUSDT_SUMCBL'):
        self._assert_legacy_sim_symbol(symbol)
        return self._request('GET','/api/mix/v1/account/account',query={'symbol':symbol,'marginCoin':'SUSDT'},private=True,paptrading=False)
    def legacy_sim_positions(self):
        return self._request('GET','/api/mix/v1/position/allPosition',query={'productType':'sumcbl','marginCoin':'SUSDT'},private=True,paptrading=False)
    def legacy_sim_place_order(self, body:dict):
        symbol=str((body or {}).get('symbol') or '').upper(); margin=str((body or {}).get('marginCoin') or '').upper()
        self._assert_legacy_sim_symbol(symbol)
        if margin!='SUSDT': raise RuntimeError('legacy simulated backend requires SUSDT')
        return self._request('POST','/api/mix/v1/order/placeOrder',body=body,private=True,paptrading=False)

    def set_hold_mode(self,mode='one_way_mode'):
        return self._request('POST','/api/v3/account/set-hold-mode',body={'holdMode':mode},private=True)
    def set_leverage(self,symbol:str,leverage='2',margin_mode='crossed'):
        return self._request('POST','/api/v3/account/set-leverage',body={'category':'USDT-FUTURES','symbol':symbol,'leverage':str(leverage),'marginMode':margin_mode},private=True)


def _floor_to_step(value:float, step:float, precision:int)->float:
    if step <= 0: step = 10 ** (-precision)
    v=Decimal(str(value)); s=Decimal(str(step))
    units=(v/s).to_integral_value(rounding=ROUND_DOWN)
    q=units*s
    quant=Decimal('1').scaleb(-precision)
    return float(q.quantize(quant,rounding=ROUND_DOWN))


def normalize_price(price:float, instrument:dict)->float:
    precision=int(instrument.get('pricePrecision') or instrument.get('pricePlace') or 8)
    step=float(instrument.get('priceMultiplier') or instrument.get('priceEndStep') or 10**(-precision))
    return _floor_to_step(price,step,precision)


def normalize_qty(qty:float, instrument:dict)->float:
    precision=int(instrument.get('quantityPrecision') or instrument.get('volumePlace') or 8)
    step=float(instrument.get('quantityMultiplier') or instrument.get('sizeMultiplier') or 10**(-precision))
    q=_floor_to_step(qty,step,precision)
    min_q=float(instrument.get('minOrderQty') or instrument.get('minTradeNum') or 0)
    max_q=float(instrument.get('maxMarketOrderQty') or instrument.get('maxOrderQty') or 0)
    if q < min_q: return 0.0
    if max_q > 0: q=min(q,max_q)
    return q
