from __future__ import annotations
from datetime import datetime, timezone
from .settings import BitgetSettings
from .rest_client import BitgetREST

def f(x):
    try: return float(x or 0)
    except Exception: return 0.0

def main():
    s=BitgetSettings.from_env()
    if s.mode!='demo' or s.live_trading:
        raise RuntimeError('TRADE_REPORT_REFUSED: DEMO only')
    r=BitgetREST(s)
    out=r._request('GET','/api/v2/mix/order/fills',
        query={'productType':'USDT-FUTURES','startTime':'1790985600000','limit':'100'},
        private=True,paptrading=True)
    rows=((out.get('data') or {}).get('fillList') or [])
    total_profit=0.0; total_fee=0.0
    print('TRADE_REPORT_BEGIN',flush=True)
    for x in sorted(rows,key=lambda z:int(z.get('cTime') or 0)):
        oid=str(x.get('clientOid') or '')
        src=str(x.get('enterPointSource') or '')
        sym=str(x.get('symbol') or '')
        profit=f(x.get('profit'))
        fee=sum(f(y.get('totalFee')) for y in (x.get('feeDetail') or []) if isinstance(y,dict))
        total_profit+=profit; total_fee+=fee
        print(
            'TRADE_FILL '
            f"ts={x.get('cTime')} symbol={sym} side={x.get('side')} tradeSide={x.get('tradeSide')} "
            f"qty={x.get('baseVolume')} price={x.get('price')} profit={profit:.8f} fee={fee:.8f} "
            f"orderId={x.get('orderId')} clientOid={oid} source={src}",
            flush=True
        )
    print(f'TRADE_REPORT_TOTAL fills={len(rows)} profit={total_profit:.8f} fee={total_fee:.8f} net={total_profit+total_fee:.8f}',flush=True)
    print('TRADE_REPORT_END',flush=True)

if __name__=='__main__':
    main()
