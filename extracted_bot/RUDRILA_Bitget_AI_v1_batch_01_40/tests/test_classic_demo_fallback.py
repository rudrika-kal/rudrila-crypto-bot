import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
os.environ['RUDRILA_MODE']='demo'; os.environ['LIVE_TRADING']='false'
from rudrila.settings import BitgetSettings
from rudrila.bitget_execution import DemoOrderExecutor
from rudrila.runtime_engine import DemoTradingRuntime
from rudrila.rest_client import BitgetREST

class ClassicFallbackTests(unittest.TestCase):
    def test_classic_susdt_equity(self):
        eq,coin=DemoTradingRuntime._usable_classic_equity([{'marginCoin':'SUSDT','available':'2980.6216','accountEquity':'0'}])
        self.assertAlmostEqual(eq,2980.6216); self.assertEqual(coin,'SUSDT')
    def test_classic_usdt_equity(self):
        eq,coin=DemoTradingRuntime._usable_classic_equity([{'marginCoin':'USDT','equity':'1200'}])
        self.assertEqual(eq,1200); self.assertEqual(coin,'USDT')
    def test_demo_display_symbol(self):
        self.assertEqual(DemoTradingRuntime._demo_display_symbol('BTCUSDT'),'SBTCSUSDT')
        self.assertEqual(DemoTradingRuntime._demo_display_symbol('ETHUSDT'),'SETHSUSDT')
    def test_same_market(self):
        self.assertTrue(DemoTradingRuntime._same_market('SBTCSUSDT','BTCUSDT'))
        self.assertTrue(DemoTradingRuntime._same_market('SETHSUSDT','ETHUSDT'))
    def test_classic_order_shape(self):
        e=DemoOrderExecutor(BitgetSettings.from_env())
        b=e.build_classic_order('BTCUSDT','buy',.001,oid='x1',margin_coin='SUSDT',take_profit=90000,stop_loss=80000)
        self.assertEqual(b['productType'],'USDT-FUTURES'); self.assertEqual(b['marginCoin'],'SUSDT')
        self.assertEqual(b['tradeSide'],'open'); self.assertEqual(b['presetStopSurplusPrice'],'90000')
        self.assertEqual(b['presetStopLossPrice'],'80000')
    def test_classic_rest_paths(self):
        calls=[]
        class R(BitgetREST):
            def _request(self,method,path,**kw): calls.append((method,path,kw)); return {'data':[]}
        r=R(BitgetSettings.from_env()); r.classic_accounts(); r.classic_positions(margin_coin='SUSDT')
        self.assertEqual(calls[0][1],'/api/v2/mix/account/accounts')
        self.assertEqual(calls[1][2]['query']['marginCoin'],'SUSDT')

if __name__=='__main__': unittest.main()
