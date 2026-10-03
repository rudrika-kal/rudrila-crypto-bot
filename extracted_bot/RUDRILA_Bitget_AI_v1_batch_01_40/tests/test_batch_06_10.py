import sys, unittest, math, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from rudrila.trend import TrendFamily
from rudrila.momentum import MomentumFamily
from rudrila.structure_fib import StructureFibFamily
from rudrila.order_flow import OrderFlowFamily
from rudrila.volume_derivatives import VolumeDerivativesFamily
from rudrila.ws_public import BitgetPublicDemoWS
from rudrila.settings import BitgetSettings
from rudrila.engine_06_10 import SignalEngine0610

def candle(p, delta=.2, v=100):
    o=p-delta/2
    c=p+delta/2
    return o,max(o,c)+.15,min(o,c)-.15,c,v

class T(unittest.TestCase):
    def test_06_trend_rising(self):
        x=TrendFamily()
        s=None
        for i in range(350):
            p=100+i*.08
            s=x.update(*candle(p,.08,100+i%5))
        self.assertEqual(s.direction,'LONG')
        self.assertGreater(s.long,s.short)
        self.assertIn('adx',x.last)

    def test_06_trend_falling(self):
        x=TrendFamily()
        for i in range(350):
            p=140-i*.08
            s=x.update(*candle(p,-.08,100+i%5))
        self.assertEqual(s.direction,'SHORT')
        self.assertGreater(s.short,s.long)

    def test_07_momentum_rising(self):
        x=MomentumFamily()
        for i in range(80):
            p=100+i*.12
            s=x.update(*candle(p,.15,100))
        self.assertGreaterEqual(s.long,s.short)
        self.assertIn('macd_hist',x.last)
        self.assertTrue(0 <= x.last['stoch_rsi'] <= 100)

    def test_07_scores_bounded(self):
        x=MomentumFamily()
        for i in range(100):
            p=100+math.sin(i/3)*3
            s=x.update(*candle(p,math.sin(i)*.8,100))
        self.assertTrue(0<=s.long<=100 and 0<=s.short<=100)

    def test_08_fibonacci_math_up(self):
        f=StructureFibFamily.fibonacci(100,200,'UP')
        self.assertAlmostEqual(f.levels['50.0'],150)
        self.assertAlmostEqual(f.levels['61.8'],138.2)
        self.assertAlmostEqual(f.extensions['161.8'],261.8)

    def test_08_fibonacci_math_down(self):
        f=StructureFibFamily.fibonacci(100,200,'DOWN')
        self.assertAlmostEqual(f.levels['50.0'],150)
        self.assertAlmostEqual(f.levels['61.8'],161.8)
        self.assertAlmostEqual(f.extensions['161.8'],38.2)

    def test_08_structure_tracks_swing(self):
        x=StructureFibFamily(lookback=30)
        for i in range(35):
            p=100+i
            s=x.update(p-.2,p+.5,p-.5,p+.2,100,atr=1)
        self.assertIsNotNone(x.last_map)
        self.assertEqual(x.last_map.direction,'UP')
        self.assertGreater(x.last_map.swing_high,x.last_map.swing_low)

    def test_09_orderbook_buy_imbalance(self):
        book={'b':[['100','10'],['99','8']], 'a':[['101','1'],['102','1']]}
        trades=[{'price':'100','size':'2','side':'buy'} for _ in range(10)]
        s=OrderFlowFamily().score(book,trades,100,101)
        self.assertEqual(s.direction,'LONG')
        self.assertGreater(s.long,s.short)

    def test_09_orderflow_spread_veto(self):
        s=OrderFlowFamily(max_spread_pct=.05).score({'b':[['100','1']],'a':[['101','1']]},[],100,101)
        self.assertTrue(s.veto)

    def test_09_sell_delta(self):
        book={'b':[['100','2']], 'a':[['100.01','2']]}
        trades=[{'price':'100','size':'2','side':'sell'} for _ in range(20)]
        s=OrderFlowFamily().score(book,trades,100,100.01)
        self.assertGreater(s.short,s.long)

    def test_10_volume_oi_confirmation(self):
        x=VolumeDerivativesFamily()
        x.update(100,100,0.0,10000)
        s=x.update(101,250,0.0,10100)
        self.assertGreater(s.long,s.short)
        self.assertGreater(x.last['oi_delta'],0)

    def test_10_funding_crowding_penalty(self):
        x=VolumeDerivativesFamily()
        x.update(100,100,0,10000)
        normal=x.update(101,200,0,10100)
        y=VolumeDerivativesFamily()
        y.update(100,100,0,10000)
        crowded=y.update(101,200,.002,10100)
        self.assertLess(crowded.long,normal.long)

    def test_10_ws_ticker_derivatives_fields(self):
        s=BitgetSettings.from_env()
        w=BitgetPublicDemoWS(s,symbols=('BTCUSDT',))
        w.handle({'arg':{'symbol':'BTCUSDT','topic':'ticker'},'ts':1234567890000,
                  'data':[{'lastPrice':'100','bid1Price':'99.9','ask1Price':'100.1',
                           'markPrice':'100.02','indexPrice':'99.98','fundingRate':'0.0001',
                           'openInterest':'12345','nextFundingTime':'1234567999999',
                           'volume24h':'9876'}]})
        st=w.states['BTCUSDT']
        self.assertEqual(st.open_interest,12345.0)
        self.assertAlmostEqual(st.funding_rate,.0001)
        self.assertEqual(st.mark_price,100.02)

    def test_integrated_five_families(self):
        e=SignalEngine0610()
        book={'b':[['100','3']], 'a':[['100.01','1']]}
        trades=[{'price':'100','size':'1','side':'buy'}]*10
        scores=None
        for i in range(100):
            p=100+i*.05
            o,h,l,c,v=candle(p,.08,100+i%10)
            scores=e.update_candle(o,h,l,c,v,book=book,trades=trades,bid=100,ask=100.01,
                                   funding_rate=.0001,open_interest=10000+i*2)
        self.assertEqual(set(scores),{'trend','momentum','structure_fibonacci','order_flow','volume_derivatives'})
        for s in scores.values():
            self.assertTrue(0<=s.long<=100 and 0<=s.short<=100)

    def test_fast_incremental_benchmark(self):
        e=SignalEngine0610()
        book={'b':[['100','2']], 'a':[['100.01','2']]}
        start=time.perf_counter()
        for i in range(5000):
            p=100+math.sin(i/50)
            o,h,l,c,v=candle(p,.05,100+i%20)
            e.update_candle(o,h,l,c,v,book=book,trades=(),bid=100,ask=100.01,
                            funding_rate=0.0,open_interest=10000+i*.01)
        elapsed=time.perf_counter()-start
        self.assertLess(elapsed,5.0)

if __name__=='__main__':
    unittest.main()
