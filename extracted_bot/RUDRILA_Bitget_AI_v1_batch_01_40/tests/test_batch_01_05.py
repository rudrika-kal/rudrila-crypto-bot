import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from rudrila.settings import BitgetSettings,load_config
from rudrila.indicators import FastIndicatorPack
from rudrila.market_state import SymbolState
from rudrila.bitget_auth import SignedRequest
from rudrila.ws_public import BitgetPublicDemoWS
class T(unittest.TestCase):
 def setUp(self): os.environ['RUDRILA_MODE']='demo'; os.environ['LIVE_TRADING']='false'; os.environ.pop('BITGET_DEMO_API_KEY',None); os.environ.pop('BITGET_DEMO_API_SECRET',None); os.environ.pop('BITGET_DEMO_API_PASSPHRASE',None)
 def test_demo_only(self): self.assertFalse(BitgetSettings.from_env().live_trading)
 def test_live_rejected(self):
  os.environ['LIVE_TRADING']='true'
  with self.assertRaises(RuntimeError): BitgetSettings.from_env()
 def test_weights(self): self.assertEqual(sum(load_config()['decision']['families'].values()),100)
 def test_indicators(self):
  p=FastIndicatorPack(); price=100.
  for i in range(300): price+=.05; out=p.update_candle(price-.1,price+.2,price-.2,price,10+i%7)
  self.assertGreater(out['ema9'],out['ema50']); self.assertGreater(out['atr14'],0); self.assertTrue(0<=out['rsi14']<=100)
 def test_spread(self):
  s=SymbolState('BTCUSDT',bid=99,ask=101); s.touch(); self.assertAlmostEqual(s.spread_pct,2.0); self.assertFalse(s.is_stale(3000))
 def test_auth_missing(self):
  with self.assertRaises(RuntimeError): SignedRequest('GET','/api/v3/account/assets').headers(BitgetSettings.from_env())
 def test_subscriptions(self): self.assertEqual(len(BitgetPublicDemoWS(BitgetSettings.from_env()).subscriptions()),12)
 def test_gate(self):
  c=load_config(); self.assertEqual(c['decision']['base_entry_score'],82); self.assertEqual(c['decision']['minimum_aligned_families'],5); self.assertFalse(c['decision']['force_trade'])
if __name__=='__main__': unittest.main()
