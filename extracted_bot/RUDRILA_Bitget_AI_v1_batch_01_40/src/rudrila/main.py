from __future__ import annotations
import argparse,asyncio,json,sys
from .settings import BitgetSettings,load_config
from .ws_public import BitgetPublicDemoWS
from .rest_client import BitgetREST
from .preflight import Preflight
from .bitget_execution import DemoOrderExecutor
from .private_ws import BitgetPrivateDemoWS
from .runtime_engine import DemoTradingRuntime

def main():
    ap=argparse.ArgumentParser(description='RUDRILA Bitget AI — DEMO ONLY')
    ap.add_argument('--show-config',action='store_true')
    ap.add_argument('--public-smoke',type=int,metavar='SECONDS')
    ap.add_argument('--public-preflight',action='store_true')
    ap.add_argument('--private-preflight',action='store_true')
    ap.add_argument('--private-ws-smoke',type=int,metavar='SECONDS')
    ap.add_argument('--demo-run',type=int,metavar='SECONDS')
    ap.add_argument('--forward-report',type=int,metavar='DAYS')
    ap.add_argument('--history-smoke',action='store_true')
    a=ap.parse_args(); s=BitgetSettings.from_env(); c=load_config()
    if a.show_config: print(json.dumps(c,indent=2)); return
    if a.public_preflight:
        print(json.dumps(Preflight(BitgetREST(s),c['symbols']).run_public(),indent=2)); return
    if a.private_preflight:
        s.require_demo_credentials(); print(json.dumps(Preflight(BitgetREST(s),c['symbols']).run_private(),indent=2)); return
    if a.public_smoke:
        async def go():
            states=await BitgetPublicDemoWS(s).run_once(a.public_smoke)
            for sym,st in states.items(): print(sym,{'last':st.last_price,'bid':st.bid,'ask':st.ask,'spread_pct':st.spread_pct,'stale':st.is_stale(),'trades_cached':len(st.trades),'candles_1m':len(st.candles['1m'])})
        asyncio.run(go()); return
    if a.private_ws_smoke:
        s.require_demo_credentials(); e=DemoOrderExecutor(s); p=BitgetPrivateDemoWS(e)
        async def go2():
            task=asyncio.create_task(p.run())
            await asyncio.sleep(a.private_ws_smoke)
            print(json.dumps({'connected':p.connected,'logged_in':p.logged_in,'orders':len(e.state.orders),'fills':len(e.state.fills),'positions':len(e.state.positions)},indent=2))
            p.stop(); task.cancel()
        asyncio.run(go2()); return
    if a.forward_report is not None:
        from .forward_report import report
        print(json.dumps(report(days_running=a.forward_report),indent=2)); return
    if a.history_smoke:
        from .history_runner import fetch_range
        import time as _t
        end=int(_t.time()*1000); start=end-60*60*1000
        rows=fetch_range(BitgetREST(s),'BTCUSDT','1m',start,end)
        print(json.dumps({'symbol':'BTCUSDT','interval':'1m','rows':len(rows),'first':rows[0][0] if rows else None,'last':rows[-1][0] if rows else None},indent=2)); return
    if a.demo_run:
        s.require_demo_credentials(); ws=BitgetPublicDemoWS(s,c['symbols']); rt=DemoTradingRuntime(s,c)
        asyncio.run(rt.run(ws,a.demo_run)); return
    print('RUDRILA Bitget AI is ready in DEMO mode. Run --public-preflight now; after adding Demo API credentials run --private-preflight, then --demo-run 3600.')
if __name__=='__main__': main()
