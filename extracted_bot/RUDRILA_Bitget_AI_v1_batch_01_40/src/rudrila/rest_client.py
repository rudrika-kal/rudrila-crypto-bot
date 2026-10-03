from __future__ import annotations
import json, urllib.parse, urllib.request, urllib.error
from decimal import Decimal, ROUND_DOWN
from .settings import BitgetSettings
from .bitget_auth import SignedRequest

class BitgetREST:
    def __init__(self, settings: BitgetSettings, timeout: int = 12):
        self.s=settings; self.timeout=timeout

    def _request(self, method:str, path:str, *, query:dict|None=None, body:dict|None=None, private=False, paptrading=True):
        query=query or None
        qs=('?'+urllib.parse.urlencode(query)) if query else ''
        raw=json.dumps(body,separators=(',',':')) if body is not None else ''
        headers={'Content-Type':'application/json','User-Agent':'RUDRILA-Bitget-AI/1.1'}
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
                out=json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raw_err=e.read().decode(errors='replace')
            try:
                parsed=json.loads(raw_err)
                raise RuntimeError(f"Bitget HTTP {e.code} code={parsed.get('code')} msg={parsed.get('msg')} data={parsed.get('data')}") from e
            except json.JSONDecodeError:
                raise RuntimeError(f"Bitget HTTP {e.code}: {raw_err[:500]}") from e
        if str(out.get('code')) not in ('00000','0'):
            raise RuntimeError(f'Bitget API error {out}')
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
    # Classic Futures Demo fallback. Some Bitget mobile Demo accounts expose
    # SUSDT/SBTC... synthetic assets while UTA v3 reports zero equity. These
    # endpoints use the same Demo API key and paptrading=1 header.
    def classic_accounts(self, product_type='USDT-FUTURES'):
        return self._request('GET','/api/v2/mix/account/accounts',query={'productType':product_type},private=True)
    def classic_positions(self, product_type='USDT-FUTURES', margin_coin=None):
        q={'productType':product_type}
        if margin_coin: q['marginCoin']=margin_coin
        return self._request('GET','/api/v2/mix/position/all-position',query=q,private=True)
    def classic_place_order(self, body:dict):
        return self._request('POST','/api/v2/mix/order/place-order',body=body,private=True)
    def classic_set_leverage(self, symbol:str, leverage='10', margin_coin='USDT'):
        return self._request('POST','/api/v2/mix/account/set-leverage',body={'symbol':symbol,'productType':'USDT-FUTURES','marginCoin':str(margin_coin).upper(),'leverage':str(leverage)},private=True)

    # Legacy simulated-coin Demo endpoints. This is Bitget's separate demo-coin
    # environment (SUSDT/SBTC/SETH, productType SUMCBL). It must NOT carry the
    # paptrading header. Hard whitelist keeps this backend incapable of touching
    # standard USDT live contracts even if a normal API key is used later.
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


def normalize_qty(qty:float, instrument:dict)->float:
    precision=int(instrument.get('quantityPrecision') or instrument.get('volumePlace') or 8)
    step=float(instrument.get('quantityMultiplier') or instrument.get('sizeMultiplier') or 10**(-precision))
    q=_floor_to_step(qty,step,precision)
    min_q=float(instrument.get('minOrderQty') or instrument.get('minTradeNum') or 0)
    max_q=float(instrument.get('maxMarketOrderQty') or instrument.get('maxOrderQty') or 0)
    if q < min_q: return 0.0
    if max_q > 0: q=min(q,max_q)
    return q
