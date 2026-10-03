import os, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
os.environ['RUDRILA_MODE']='demo'
os.environ['LIVE_TRADING']='false'

from rudrila.settings import BitgetSettings
from rudrila.ws_public import BitgetPublicDemoWS
from rudrila.volatility_execution import VolatilityExecutionFamily
from rudrila.regime import RegimeDetector
from rudrila.signals import FamilyScore
from rudrila.consensus import consensus
from rudrila.entry_rules import EntryRules

class FastMoveFixTests(unittest.TestCase):
    def test_books5_overrides_lagged_ticker_spread(self):
        w=BitgetPublicDemoWS(BitgetSettings.from_env(),symbols=('ETHUSDT',))
        w.handle({'arg':{'symbol':'ETHUSDT','topic':'ticker'},'ts':1,
                  'data':[{'bid1Price':'2600','ask1Price':'2700'}]})
        self.assertGreater(w.states['ETHUSDT'].spread_pct,0.05)
        w.handle({'arg':{'symbol':'ETHUSDT','topic':'books5'},'ts':2,
                  'data':[{'b':[['2655.0','10']], 'a':[['2655.1','10']]}]})
        self.assertLess(w.states['ETHUSDT'].spread_pct,0.05)

    def test_panic_does_not_hard_veto_when_execution_is_healthy(self):
        x=VolatilityExecutionFamily()
        for i in range(25):
            x.update(100.2,99.8,100,99.99,100.01,100000)
        s=x.update(103,97,97.2,97.19,97.21,100000)
        self.assertTrue(x.last['panic'])
        self.assertFalse(s.veto)

    def test_deep_book_wide_ticker_alone_is_not_low_liquidity(self):
        r=RegimeDetector()
        out=r.update(100,.3,30,.08,.8,False,depth_notional=500000)
        self.assertNotEqual(out,'LOW_LIQUIDITY')

    @staticmethod
    def scores(side='SHORT', strength=85):
        d={}
        for n in ('order_flow','structure_fibonacci','trend','momentum','volume_derivatives'):
            if side=='SHORT':
                d[n]=FamilyScore.build(n,5,strength)
            else:
                d[n]=FamilyScore.build(n,strength,5)
        d['news_macro']=FamilyScore.build('news_macro',0,0)
        d['volatility_execution']=FamilyScore.build('volatility_execution',20,20)
        return d

    def test_fast_impulse_short_can_enter_below_normal_composite_threshold(self):
        scores=self.scores('SHORT',82)
        c=consensus(scores)
        normal=EntryRules().decide(c,'PANIC',breaking_allow=True,risk_allow=True,cooldown=False)
        self.assertFalse(normal.enter)
        fast=EntryRules().decide_directional_core(
            c,scores,'PANIC',candle_ret_pct=-0.65,candle_range_pct=0.9,
            atr_pct=0.22,spread_pct=0.008,depth_notional=500000,
            mtf5='SHORT',mtf15='LONG',breakout_down=True,
            breaking_allow=True,risk_allow=True,cooldown=False)
        self.assertTrue(fast.enter)
        self.assertEqual(fast.side,'SHORT')
        self.assertIn('fast_impulse',fast.reason)

    def test_fast_path_keeps_execution_safety_fail_closed(self):
        scores=self.scores('SHORT',90)
        c=consensus(scores)
        fast=EntryRules().decide_directional_core(
            c,scores,'PANIC',candle_ret_pct=-0.8,candle_range_pct=1.0,
            atr_pct=0.2,spread_pct=0.06,depth_notional=500,
            mtf5='SHORT',mtf15='SHORT',breakout_down=True,
            breaking_allow=True,risk_allow=True,cooldown=False)
        self.assertFalse(fast.enter)

    def test_fast_path_requires_four_core_families(self):
        scores=self.scores('SHORT',85)
        scores['order_flow']=FamilyScore.build('order_flow',80,5)
        scores['volume_derivatives']=FamilyScore.build('volume_derivatives',80,5)
        c=consensus(scores)
        fast=EntryRules().decide_directional_core(
            c,scores,'PANIC',candle_ret_pct=-0.8,candle_range_pct=1.0,
            atr_pct=0.2,spread_pct=0.01,depth_notional=500000,
            mtf5='SHORT',mtf15='SHORT',breakout_down=True,
            breaking_allow=True,risk_allow=True,cooldown=False)
        self.assertFalse(fast.enter)

if __name__=='__main__':
    unittest.main()

class LeverageConfigTests(unittest.TestCase):
    class R:
        def classic_set_leverage(self,symbol,leverage,margin_coin):
            return {'code':'00000','data':{'symbol':symbol}}
        def classic_single_account(self,symbol,margin_coin):
            return {'code':'00000','data':{'crossMarginLeverage':'10'}}
        def set_leverage(self,symbol,leverage,margin_mode):
            return {'code':'00000'}

    def test_classic_10x_verified(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        x=DemoTradingRuntime.__new__(DemoTradingRuntime)
        x.symbols=('BTCUSDT','ETHUSDT'); x.rest=self.R()
        x.execution_backend='CLASSIC_V2_DEMO'; x.demo_margin_coin='USDT'
        x.target_leverage=10; x.leverage_ready=False; x.leverage_error=''
        x.leverage_last_ms=0; x.leverage_verified={}
        x._demo_display_symbol=DemoTradingRuntime._demo_display_symbol
        self.assertTrue(DemoTradingRuntime._configure_demo_leverage(x,force=True))
        self.assertEqual(x.leverage_verified['BTCUSDT']['leverage'],10.0)

    def test_mismatch_fails_closed(self):
        from rudrila.runtime_engine import DemoTradingRuntime
        class Bad(self.R):
            def classic_single_account(self,symbol,margin_coin):
                return {'code':'00000','data':{'crossMarginLeverage':'5'}}
        x=DemoTradingRuntime.__new__(DemoTradingRuntime)
        x.symbols=('BTCUSDT',); x.rest=Bad()
        x.execution_backend='CLASSIC_V2_DEMO'; x.demo_margin_coin='USDT'
        x.target_leverage=10; x.leverage_ready=False; x.leverage_error=''
        x.leverage_last_ms=0; x.leverage_verified={}
        x._demo_display_symbol=DemoTradingRuntime._demo_display_symbol
        self.assertFalse(DemoTradingRuntime._configure_demo_leverage(x,force=True))
        self.assertIn('mismatch',x.leverage_error)
