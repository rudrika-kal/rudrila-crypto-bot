from __future__ import annotations
import time
from .rest_client import BitgetREST

def fetch_range(rest:BitgetREST,symbol:str,interval:str,start_ms:int,end_ms:int,sleep_s=.06):
    """Paginate UTA history-candles safely (100 rows/request), dedupe by timestamp."""
    rows={}; cursor=start_ms
    # Use bounded windows; Bitget history endpoint allows max 90-day query range.
    while cursor < end_ms:
        out=rest.candles(symbol,interval,limit=100,start_ms=cursor,end_ms=end_ms,history=True)
        data=out.get('data') or []
        if not data: break
        for r in data: rows[int(r[0])]=r
        mx=max(int(r[0]) for r in data)
        if mx<=cursor: break
        cursor=mx+1
        time.sleep(sleep_s)
        if len(data)<100: break
    return [rows[k] for k in sorted(rows)]
