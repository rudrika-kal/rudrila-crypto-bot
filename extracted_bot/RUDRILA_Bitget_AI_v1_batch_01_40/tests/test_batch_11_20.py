import os,sys,unittest,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from rudrila.volatility_execution import VolatilityExecutionFamily
from rudrila.news_macro import NewsMacroEngine,NewsItem
from rudrila.breaking_news import BreakingNewsGuard
from rudrila.signals import FamilyScore
from rudrila.consensus import consensus
from rudrila.entry_rules import EntryRules
from rudrila.regime import RegimeDetector
from rudrila.risk import RiskEngine
from rudrila.exits import ExitPlanner
from rudrila.position_manager import PositionManager,ManagedPosition
from rudrila.bitget_execution import DemoOrderExecutor
from rudrila.settings import BitgetSettings

class T(unittest.TestCase):
  def test_11_normal_quality(self):
    x=VolatilityExecutionFamily()
    s=None
    for i in range(50):
      c=100+math.sin(i/7)*.1
      s=x.update(c+.1,c-.1,c,99.99,100.01,50000)
    self.assertFalse(s.veto)
    self.assertGreater(x.last['quality'],0)

  def test_11_spread_veto(self):
    x=VolatilityExecutionFamily(max_spread_pct=.05)
    s=x.update(101,99,100,99,101,50000)
    self.assertTrue(s.veto)

  def test_12_news_positive(self):
    n=NewsMacroEngine()
    now=1_800_000_000_000
    items=[NewsItem("Bitcoin ETF approved with institutional inflows","X",now-60_000)]
    s=n.aggregate(items,{"X":"tier1_media"},now)
    self.assertEqual(s.direction,"LONG")
    self.assertGreater(n.last["signed_score"],0)

  def test_12_news_negative(self):
    n=NewsMacroEngine()
    now=1_800_000_000_000
    items=[NewsItem("Major crypto exchange hack and insolvency","Y",now-60_000)]
    s=n.aggregate(items,{"Y":"tier1_media"},now)
    self.assertEqual(s.direction,"SHORT")

  def test_12_dedupe(self):
    n=NewsMacroEngine()
    now=1_800_000_000_000
    items=[NewsItem("Bitcoin ETF approved today","A",now),
           NewsItem("Today Bitcoin ETF approved","B",now)]
    self.assertEqual(len(n.dedupe(items)),1)

  def test_13_breaking_freeze_and_confirm(self):
    g=BreakingNewsGuard(freeze_ms=1000,extreme_score=70)
    g.ingest(90,"ETF approved",1000)
    self.assertFalse(g.evaluate(1500,.2,"LONG")["allow"])
    self.assertTrue(g.evaluate(2200,.2,"LONG")["allow"])

  def _scores(self,side="LONG",veto=False):
    d={}
    for n in ("order_flow","structure_fibonacci","trend","news_macro","momentum","volume_derivatives"):
      d[n]=FamilyScore.build(n,95 if side=="LONG" else 5,5 if side=="LONG" else 95)
    d["volatility_execution"]=FamilyScore.build("volatility_execution",95,95,veto=veto)
    return d

  def test_14_consensus_long(self):
    c=consensus(self._scores("LONG"))
    self.assertEqual(c.direction,"LONG")
    self.assertGreaterEqual(c.aligned_families,5)
    self.assertGreater(c.long_score,c.short_score)

  def test_14_veto_propagates(self):
    self.assertTrue(consensus(self._scores("LONG",True)).veto)

  def test_15_entry_approved(self):
    c=consensus(self._scores("LONG"))
    d=EntryRules().decide(c,"TREND")
    self.assertTrue(d.enter)

  def test_15_entry_reject_panic(self):
    c=consensus(self._scores("LONG"))
    d=EntryRules().decide(c,"PANIC")
    self.assertFalse(d.enter)

  def test_16_regime_trend(self):
    r=RegimeDetector()
    out=None
    for i in range(30):
      out=r.update(100+i*.1,.3,30,.001,.8,False)
    self.assertEqual(out,"TREND")

  def test_16_regime_low_liquidity(self):
    r=RegimeDetector()
    self.assertEqual(r.update(100,.3,10,.2,.1,False),"LOW_LIQUIDITY")

  def test_17_risk_qty(self):
    r=RiskEngine()
    x=r.assess(1000,1000,1000,100,99,"LONG",[],5)
    self.assertTrue(x.allow)
    self.assertGreater(x.qty,0)
    self.assertLessEqual(x.risk_usdt,2.5)

  def test_17_daily_loss_cap(self):
    x=RiskEngine().assess(980,1000,1000,100,99,"LONG",[],5)
    self.assertFalse(x.allow)

  def test_17_correlated_exposure(self):
    pos=[{"symbol":"BTCUSDT","side":"LONG"}]
    x=RiskEngine().assess(1000,1000,1000,100,99,"LONG",pos,5)
    self.assertFalse(x.allow)

  def test_18_exit_long(self):
    p=ExitPlanner().plan("LONG",100,1,swing_low=98,fib_extension=105)
    self.assertLess(p.stop,100); self.assertGreater(p.tp1,100); self.assertGreaterEqual(p.tp2,105)

  def test_18_exit_short(self):
    p=ExitPlanner().plan("SHORT",100,1,swing_high=102,fib_extension=95)
    self.assertGreater(p.stop,100); self.assertLess(p.tp1,100); self.assertLessEqual(p.tp2,95)

  def test_19_breakeven(self):
    p=ManagedPosition("BTCUSDT","LONG",1,100,98,103,105,2,1000)
    a=PositionManager(be_trigger_r=.8).update(p,101.7,2000,.5)
    self.assertEqual(a.action,"MOVE_STOP")
    self.assertEqual(p.stop,100)

  def test_19_partial_tp(self):
    p=ManagedPosition("BTCUSDT","LONG",1,100,98,102,105,2,1000)
    a=PositionManager().update(p,102.1,2000,.5)
    self.assertEqual(a.action,"PARTIAL_CLOSE")

  def test_20_order_builder(self):
    s=BitgetSettings.from_env()
    e=DemoOrderExecutor(s)
    b=e.build_order("BTCUSDT","buy",.001,pos_side="long",oid="abc123")
    self.assertEqual(b["category"],"USDT-FUTURES")
    self.assertEqual(b["clientOid"],"abc123")
    self.assertEqual(b["side"],"buy")

  def test_20_duplicate_guard(self):
    s=BitgetSettings.from_env()
    e=DemoOrderExecutor(s)
    e.sent_client_oids.add("dup")
    with self.assertRaises(RuntimeError):
      e.build_order("BTCUSDT","buy",.001,oid="dup")

  def test_20_private_subscriptions(self):
    s=BitgetSettings.from_env()
    e=DemoOrderExecutor(s)
    p=e.private_subscriptions()
    topics={x["topic"] for x in p["args"]}
    self.assertEqual(topics,{"order","fill","position","account"})

  def test_20_ws_reconciliation(self):
    s=BitgetSettings.from_env()
    e=DemoOrderExecutor(s)
    e.handle_private({"arg":{"topic":"fill"},"data":[{"symbol":"BTCUSDT","orderId":"1"}]})
    e.handle_private({"arg":{"topic":"position"},"data":[{"symbol":"BTCUSDT","posSide":"long","qty":"0.1"}]})
    self.assertEqual(len(e.state.fills),1)
    self.assertIn(("BTCUSDT","long"),e.state.positions)

  def test_20_ws_login_needs_key(self):
    s=BitgetSettings.from_env()
    with self.assertRaises(RuntimeError):
      DemoOrderExecutor.ws_login_payload(s,123)

if __name__=="__main__":
  unittest.main()

class BreakingNewsRepeatTests(unittest.TestCase):
 def test_same_extreme_headline_does_not_extend_freeze(self):
  from rudrila.breaking_news import BreakingNewsGuard
  g=BreakingNewsGuard(freeze_ms=60000,extreme_score=70)
  a=g.ingest(-100,'Same headline',1000)
  until=a.until_ms
  b=g.ingest(-100,'Same headline',31000)
  self.assertEqual(b.until_ms,until)
  self.assertFalse(g.evaluate(until+1,0,'NEUTRAL')['allow'])
  c=g.ingest(-100,'Same headline',until+30000)
  self.assertFalse(c.active)
 def test_new_extreme_headline_can_trigger_again(self):
  from rudrila.breaking_news import BreakingNewsGuard
  g=BreakingNewsGuard(freeze_ms=60000,extreme_score=70)
  g.ingest(-100,'Headline A',1000)
  g.evaluate(62000,0,'NEUTRAL')
  c=g.ingest(100,'Headline B',63000)
  self.assertTrue(c.active); self.assertEqual(c.direction,'LONG')
