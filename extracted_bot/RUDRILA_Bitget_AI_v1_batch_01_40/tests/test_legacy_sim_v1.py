import unittest
from rudrila.rest_client import normalize_qty, BitgetREST
from rudrila.bitget_execution import DemoOrderExecutor
from rudrila.settings import BitgetSettings
from rudrila.runtime_engine import DemoTradingRuntime

class T(unittest.TestCase):
    def settings(self):
        return BitgetSettings(mode="demo",live_trading=False,api_key="k",api_secret="s",passphrase="p")
    def test_symbol_map(self):
        self.assertEqual(DemoTradingRuntime._legacy_sim_symbol("BTCUSDT"),"SBTCSUSDT_SUMCBL")
        self.assertEqual(DemoTradingRuntime._legacy_sim_symbol("ETHUSDT"),"SETHSUSDT_SUMCBL")
    def test_hard_demo_only_order(self):
        ex=DemoOrderExecutor(self.settings())
        b=ex.build_legacy_sim_order("SBTCSUSDT_SUMCBL","buy",0.001,take_profit=90000,stop_loss=80000)
        self.assertEqual(b["marginCoin"],"SUSDT"); self.assertEqual(b["side"],"open_long")
        with self.assertRaises(RuntimeError): ex.build_legacy_sim_order("BTCUSDT_UMCBL","buy",0.001)
    def test_legacy_precision(self):
        ins={"volumePlace":"3","sizeMultiplier":"0.001","minTradeNum":"0.001"}
        self.assertEqual(normalize_qty(0.0017,ins),0.001)
    def test_equity(self):
        self.assertEqual(DemoTradingRuntime._usable_classic_equity({"marginCoin":"SUSDT","available":"2980.6216"})[0],2980.6216)

if __name__=='__main__': unittest.main()
