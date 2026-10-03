import os,sys,unittest,json,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
os.environ['RUDRILA_MODE']='demo'; os.environ['LIVE_TRADING']='false'
from rudrila.settings import BitgetSettings
from rudrila.rest_client import normalize_qty
from rudrila.preflight import Preflight
from rudrila.bitget_execution import DemoOrderExecutor
from rudrila.private_ws import BitgetPrivateDemoWS
from rudrila.news_feeds import DEFAULT_FEEDS,SOURCE_CLASSES
from rudrila.health import HealthState

class FakeREST:
    def server_time(self): return {'data':{'serverTime':str(int(time.time()*1000))}}
    def instruments(self,s): return {'data':[{'symbol':s,'status':'online'}]}
    def account_info(self): return {'data':{'permissions':['uta_trade','uta_mgt'],'permType':'read-and-write'}}
    def account_settings(self): return {'data':{'holdMode':'one_way_mode'}}
    def account_assets(self): return {'data':[{'coin':'USDT','usdValue':'1000'}]}

class T(unittest.TestCase):
    def test_public_preflight(self): self.assertTrue(Preflight(FakeREST()).run_public()['pass'])
    def test_private_preflight(self): self.assertTrue(Preflight(FakeREST()).run_private()['pass'])
    def test_private_preflight_rejects_withdraw(self):
        f=FakeREST(); f.account_info=lambda:{'data':{'permissions':['uta_trade','withdraw'],'permType':'read-and-write'}}
        self.assertFalse(Preflight(f).run_private()['pass'])
    def test_qty_multiplier(self):
        ins={'quantityPrecision':'3','quantityMultiplier':'0.005','minOrderQty':'0.005','maxMarketOrderQty':'1'}
        self.assertAlmostEqual(normalize_qty(.0189,ins),.015)
    def test_qty_below_min(self):
        self.assertEqual(normalize_qty(.001,{'quantityPrecision':'3','quantityMultiplier':'0.001','minOrderQty':'0.005'}),0)
    def test_news_feeds(self):
        self.assertIn('Federal Reserve',DEFAULT_FEEDS); self.assertEqual(SOURCE_CLASSES['SEC'],'regulator')
    def test_private_ws_requires_creds_at_login_payload(self):
        s=BitgetSettings.from_env(); e=DemoOrderExecutor(s); p=BitgetPrivateDemoWS(e)
        with self.assertRaises(RuntimeError): e.ws_login_payload(s)
    def test_health_write(self):
        with tempfile.TemporaryDirectory() as d:
            h=HealthState(Path(d)/'h.json'); h.write({'status':'running'}); self.assertEqual(h.read()['status'],'running')
    def test_account_reconcile(self):
        s=BitgetSettings.from_env(); e=DemoOrderExecutor(s)
        e.handle_private({'arg':{'topic':'account'},'data':[{'totalEquity':'1000'}]})
        self.assertEqual(e.state.account[0]['totalEquity'],'1000')

if __name__=='__main__': unittest.main()

class ProtectionTests(unittest.TestCase):
    def test_protective_order_fields(self):
        s=BitgetSettings.from_env(); e=DemoOrderExecutor(s)
        b=e.build_order('BTCUSDT','buy',.001,oid='protect1',take_profit=105,stop_loss=95)
        self.assertEqual(b['takeProfit'],'105')
        self.assertEqual(b['stopLoss'],'95')
        self.assertEqual(b['tpOrderType'],'market')
        self.assertEqual(b['slTriggerBy'],'mark')

class MTFTests(unittest.TestCase):
    def test_mtf_trend_alignment(self):
        from rudrila.mtf import MultiTimeframeTrend
        x=MultiTimeframeTrend()
        for i in range(300):
            p=100+i*.05; vals=(p-.02,p+.1,p-.1,p+.02,100)
            x.update_1m(*vals); x.update_5m(*vals); x.update_15m(*vals)
        s=x.score(); self.assertEqual(s.direction,'LONG'); self.assertEqual(x.last['15m'],'LONG')
    def test_history_limit_capped(self):
        from rudrila.rest_client import BitgetREST
        # verify source-level behavior without network using a subclass
        class X(BitgetREST):
            def _request(self,method,path,**kw): return {'path':path,'query':kw['query']}
        r=X(BitgetSettings.from_env()); out=r.candles('BTCUSDT','1m',limit=1000,history=True)
        self.assertEqual(out['query']['limit'],'100')

class FinalWireTests(unittest.TestCase):
    def test_history_runner_paginates(self):
        from rudrila.history_runner import fetch_range
        class R:
            def __init__(self): self.n=0
            def candles(self,*a,**kw):
                self.n+=1
                if self.n==1: return {'data':[[str(i),'1','1','1','1','1'] for i in range(1,101)]}
                return {'data':[[str(i),'1','1','1','1','1'] for i in range(101,121)]}
        r=R(); rows=fetch_range(r,'BTCUSDT','1m',0,1000,sleep_s=0); self.assertEqual(len(rows),120)
    def test_forward_report_small_sample_fails(self):
        import sqlite3,tempfile
        from rudrila.journal import TradeJournal
        from rudrila.forward_report import report
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'j.db'); j=TradeJournal(p); j.close(); x=report(p,days_running=1); self.assertFalse(x['acceptance']['pass'])

class EquityParsingTests(unittest.TestCase):
    def test_uta_rest_object_equity(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        d={'totalEquity':'0','assets':[{'coin':'USDT','usdValue':'0','available':'0','bonus':'50000'}]}
        self.assertEqual(DemoTradingRuntime._usable_equity(d),50000.0)
    def test_uta_private_coin_equity(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        d=[{'totalEquity':'1200','coin':[{'coin':'USDT','usdValue':'1200','bonus':'0'}]}]
        self.assertEqual(DemoTradingRuntime._usable_equity(d),1200.0)

    def test_demo_susdt_equity(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        d=[{'totalEquity':'0','coin':[{'coin':'SUSDT','usdValue':'0','available':'2980.6216','balance':'2980.6216','bonus':'0'}]}]
        self.assertAlmostEqual(DemoTradingRuntime._usable_equity(d),2980.6216)

    def test_zero_equity_is_not_fabricated(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        self.assertEqual(DemoTradingRuntime._usable_equity({'totalEquity':'0','assets':[]}),0.0)
