from __future__ import annotations
import json, urllib.parse, urllib.request

BASE='https://api.bitget.com'
PATH='/api/v3/market/history-candles'

def history_url(symbol:str, interval:str, *, category='USDT-FUTURES', start_ms:int|None=None,
                end_ms:int|None=None, limit:int=100)->str:
    q={'category':category,'symbol':symbol,'interval':interval,'limit':str(limit)}
    if start_ms is not None: q['startTime']=str(start_ms)
    if end_ms is not None: q['endTime']=str(end_ms)
    return BASE+PATH+'?'+urllib.parse.urlencode(q)

def fetch_history(*args, timeout=12, **kwargs):
    u=history_url(*args,**kwargs)
    req=urllib.request.Request(u,headers={'User-Agent':'RUDRILA-Bitget-AI/1.0'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())
