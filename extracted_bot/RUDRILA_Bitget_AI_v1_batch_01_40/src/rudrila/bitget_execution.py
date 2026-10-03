from __future__ import annotations
import base64, hashlib, hmac, json, time, uuid, urllib.request
from dataclasses import dataclass, field
from .settings import BitgetSettings
from .bitget_auth import SignedRequest

PLACE_ORDER_PATH="/api/v3/trade/place-order"

def client_oid(symbol:str, side:str)->str:
    return f"RUD-{symbol[:4]}-{side[0]}-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

@dataclass
class ExecutionState:
    orders: dict = field(default_factory=dict)
    fills: list = field(default_factory=list)
    positions: dict = field(default_factory=dict)
    account: list = field(default_factory=list)

class DemoOrderExecutor:
    def __init__(self,settings:BitgetSettings):
        if settings.mode!="demo" or settings.live_trading:
            raise RuntimeError("DemoOrderExecutor is DEMO ONLY")
        self.s=settings
        self.state=ExecutionState()
        self.sent_client_oids=set()

    def build_order(self,symbol:str,side:str,qty:float,order_type="market",
                    price:float|None=None,reduce_only=False,pos_side:str|None=None,
                    oid:str|None=None,take_profit:float|None=None,stop_loss:float|None=None)->dict:
        if side not in ("buy","sell"): raise ValueError("side")
        if qty<=0: raise ValueError("qty")
        oid=oid or client_oid(symbol,side)
        if oid in self.sent_client_oids:
            raise RuntimeError("duplicate clientOid")
        body={
          "category":"USDT-FUTURES","symbol":symbol,"qty":format(qty,".12g"),
          "side":side,"orderType":order_type,"clientOid":oid
        }
        if pos_side:
            body["posSide"]=pos_side
        if order_type=="limit":
            if price is None or price<=0: raise ValueError("limit price required")
            body["price"]=format(price,".12g")
            body["timeInForce"]="gtc"
        if reduce_only:
            body["reduceOnly"]="yes"
        if take_profit is not None:
            body["takeProfit"]=format(float(take_profit),".12g")
            body["tpTriggerBy"]="mark"
            body["tpOrderType"]="market"
        if stop_loss is not None:
            body["stopLoss"]=format(float(stop_loss),".12g")
            body["slTriggerBy"]="mark"
            body["slOrderType"]="market"
        return body

    def signed_rest(self,method:str,path:str,body:dict|None=None):
        raw=json.dumps(body,separators=(",",":")) if body else ""
        req=SignedRequest(method,path,body=raw)
        return req.headers(self.s),raw

    def place_order(self,body:dict, timeout=12)->dict:
        # This method requires the user's Demo API key; not invoked by unit tests.
        oid=body["clientOid"]
        if oid in self.sent_client_oids:
            raise RuntimeError("duplicate clientOid")
        headers,raw=self.signed_rest("POST",PLACE_ORDER_PATH,body)
        r=urllib.request.Request(self.s.rest_base+PLACE_ORDER_PATH,data=raw.encode(),
                                 headers=headers,method="POST")
        with urllib.request.urlopen(r,timeout=timeout) as resp:
            out=json.loads(resp.read().decode())
        if str(out.get("code")) not in ("00000","0"):
            raise RuntimeError(f"Bitget order rejected: {out}")
        self.sent_client_oids.add(oid)
        # ACK is not treated as a fill. Private WS must reconcile actual state.
        self.state.orders[oid]={"ack":out,"status":"ACK_ONLY"}
        return out


    def build_classic_order(self,symbol:str,side:str,qty:float,order_type="market",
                            price:float|None=None,oid:str|None=None,margin_coin:str="SUSDT",
                            take_profit:float|None=None,stop_loss:float|None=None)->dict:
        """Build a Classic Futures Demo order for the mobile Demo account.

        Bitget's classic demo account may show SUSDT and synthetic display
        symbols in the app. The API itself normally accepts the base symbol
        (BTCUSDT/ETHUSDT) with paptrading=1; runtime retries the synthetic
        display symbol only when the base symbol is explicitly rejected.
        """
        if side not in ("buy","sell"): raise ValueError("side")
        if qty<=0: raise ValueError("qty")
        oid=oid or client_oid(symbol,side)
        if oid in self.sent_client_oids: raise RuntimeError("duplicate clientOid")
        body={
          "symbol":symbol,"productType":"USDT-FUTURES","marginMode":"crossed",
          "marginCoin":margin_coin,"size":format(qty,".12g"),"side":side,
          "tradeSide":"open","orderType":order_type,"force":"gtc","clientOid":oid
        }
        if order_type=="limit":
            if price is None or price<=0: raise ValueError("limit price required")
            body["price"]=format(price,".12g")
        if take_profit is not None: body["presetStopSurplusPrice"]=format(float(take_profit),".12g")
        if stop_loss is not None: body["presetStopLossPrice"]=format(float(stop_loss),".12g")
        return body

    def build_legacy_sim_order(self,symbol:str,side:str,qty:float,order_type='market',
                               price:float|None=None,oid:str|None=None,
                               take_profit:float|None=None,stop_loss:float|None=None)->dict:
        allowed={'SBTCSUSDT_SUMCBL','SETHSUSDT_SUMCBL'}
        symbol=str(symbol).upper()
        if symbol not in allowed: raise RuntimeError('legacy simulated backend rejects non-demo symbol')
        if side not in ('buy','sell'): raise ValueError('side')
        if qty<=0: raise ValueError('qty')
        oid=oid or client_oid(symbol,side)
        if oid in self.sent_client_oids: raise RuntimeError('duplicate clientOid')
        body={
          'symbol':symbol,'marginCoin':'SUSDT','size':format(qty,'.12g'),
          'side':'open_long' if side=='buy' else 'open_short',
          'orderType':order_type,'timeInForceValue':'normal','clientOid':oid
        }
        if order_type=='limit':
            if price is None or price<=0: raise ValueError('limit price required')
            body['price']=format(price,'.12g')
        if take_profit is not None: body['presetTakeProfitPrice']=format(float(take_profit),'.12g')
        if stop_loss is not None: body['presetStopLossPrice']=format(float(stop_loss),'.12g')
        return body

    def record_legacy_ack(self,body:dict,out:dict):
        oid=body['clientOid']
        if oid in self.sent_client_oids: raise RuntimeError('duplicate clientOid')
        self.sent_client_oids.add(oid)
        self.state.orders[oid]={'ack':out,'status':'ACK_ONLY','backend':'LEGACY_SIM_V1'}
        return out

    def record_external_ack(self,body:dict,out:dict):
        oid=body["clientOid"]
        if oid in self.sent_client_oids: raise RuntimeError("duplicate clientOid")
        self.sent_client_oids.add(oid)
        self.state.orders[oid]={"ack":out,"status":"ACK_ONLY","backend":"CLASSIC_V2_DEMO"}
        return out

    @staticmethod
    def ws_login_payload(s:BitgetSettings, timestamp_ms:int|None=None)->dict:
        if not (s.api_key and s.api_secret and s.passphrase):
            raise RuntimeError("Demo API credentials are not configured.")
        ts=str(timestamp_ms or int(time.time()*1000))
        msg=ts+"GET"+"/user/verify"
        sign=base64.b64encode(hmac.new(s.api_secret.encode(),msg.encode(),hashlib.sha256).digest()).decode()
        return {"op":"login","args":[{"apiKey":s.api_key,"passphrase":s.passphrase,
                                     "timestamp":ts,"sign":sign}]}

    @staticmethod
    def private_subscriptions()->dict:
        return {"op":"subscribe","args":[
          {"instType":"UTA","topic":"order"},
          {"instType":"UTA","topic":"fill"},
          {"instType":"UTA","topic":"position"},
          {"instType":"UTA","topic":"account"},
        ]}

    def handle_private(self,msg:dict):
        arg=msg.get("arg") or {}
        topic=arg.get("topic")
        data=msg.get("data") or []
        if topic=="order":
            for d in data:
                oid=d.get("clientOid") or d.get("clientOid".lower()) or d.get("orderId")
                if oid: self.state.orders[oid]=d
        elif topic=="fill":
            self.state.fills.extend(data)
        elif topic=="position":
            for d in data:
                sym=d.get("symbol")
                side=d.get("posSide") or d.get("side") or "net"
                if sym: self.state.positions[(sym,side)]=d
        elif topic=="account":
            self.state.account=data
        return self.state
