import os,sys,tempfile,unittest,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from rudrila.safety_layer import EmergencySafetyLayer
from rudrila.accounting import AccountingEngine,TradeLedger
from rudrila.journal import TradeJournal
from rudrila.market_history import history_url
from rudrila.backtest import Backtester,Bar,Signal
from rudrila.optimization import parameter_grid,sweep
from rudrila.validation import chronological_split,no_overlap
from rudrila.walkforward import windows,walk_forward
from rudrila.stress import run_stress_suite
from rudrila.demo_forward import ForwardStats,DemoForwardGate
from rudrila.performance import metrics,PerformanceGate
from rudrila.refinement import recommendations
from rudrila.health import HealthState
from rudrila.alerts import AlertManager
from rudrila.acceptance import DemoAcceptanceGate
from rudrila.live_lock import live_allowed
from rudrila.live_validation import plan
from rudrila.versioning import backup_files
from rudrila.audit import audit_tree
from rudrila.improvement import review

class T(unittest.TestCase):
 def test_21_safety_stale(self):
  d=EmergencySafetyLayer().evaluate(now_ms=5000,last_market_ms=1,spread_pct=.01,expected_slippage_pct=.01,ws_connected=True,account_synced=True)
  self.assertFalse(d.allow_new_entries); self.assertIn('stale market data',d.reasons)
 def test_21_safety_error_counter(self):
  s=EmergencySafetyLayer(max_api_errors=2); s.record_api_error(); s.record_api_error()
  d=s.evaluate(now_ms=10,last_market_ms=10,spread_pct=.01,expected_slippage_pct=.01,ws_connected=True,account_synced=True)
  self.assertFalse(d.allow_new_entries)
 def test_22_accounting_round_trip_cost(self):
  a=AccountingEngine(taker_fee_pct=.1,slippage_pct=.05); en,c1=a.fill('LONG',100,1,opening=True); ex,c2=a.fill('LONG',101,1,opening=False)
  l=TradeLedger('LONG',1,100,en,c1.fee,101,ex,c2.fee)
  self.assertLess(l.net_pnl(),1.0); self.assertGreater(l.total_costs(),0)
 def test_22_funding(self):
  l=TradeLedger('LONG',1,100,100,.1,101,101,.1,funding=.05); self.assertAlmostEqual(l.net_pnl(),.85)
 def test_23_journal(self):
  with tempfile.TemporaryDirectory() as d:
   j=TradeJournal(Path(d)/'j.db'); did=j.log_decision(ts_ms=1,symbol='BTCUSDT',regime='TREND',side='LONG',composite=90,aligned=6,news=10,families={'trend':90},reason='x',entered=True)
   j.log_trade(trade_id='t1',symbol='BTCUSDT',side='LONG',opened_ms=1,closed_ms=2,entry=100,exit=101,qty=1,gross_pnl=1,fees=.1,funding=0,slippage=.1,net_pnl=.8,exit_reason='TP',decision_id=did)
   self.assertEqual(j.summary()['trades'],1); j.close()
 def test_24_history_url(self):
  u=history_url('BTCUSDT','1m',start_ms=1,end_ms=2,limit=100); self.assertIn('/api/v3/market/history-candles',u); self.assertIn('BTCUSDT',u)
 def test_24_next_bar_execution(self):
  bars=[Bar(i,100+i,101+i,99+i,100+i,10) for i in range(6)]
  def strat(hist,eq):
   if len(hist)==1: return Signal('LONG',99,105,90)
   return Signal()
  r=Backtester().run(bars,strat); self.assertTrue(r.trades); self.assertNotEqual(r.trades[0]['entry'],bars[0].open)
 def test_24_conservative_both_hit(self):
  bars=[Bar(1,100,100,100,100,10),Bar(2,100,106,94,100,10),Bar(3,100,100,100,100,10)]
  def strat(hist,eq): return Signal('LONG',95,105,90) if len(hist)==1 else Signal()
  r=Backtester(accounting=AccountingEngine(taker_fee_pct=0,slippage_pct=0)).run(bars,strat); self.assertEqual(r.trades[0]['reason'],'STOP')
 def test_25_grid(self): self.assertEqual(len(list(parameter_grid({'a':[1,2],'b':[3,4]}))),4)
 def test_25_sweep(self):
  x=sweep({'a':[1,2]},lambda p:{'net_pnl':p['a'],'max_drawdown':0}); self.assertEqual(x[0]['params']['a'],2)
 def test_26_split(self):
  a,b,c=chronological_split(list(range(100))); self.assertEqual((len(a),len(b),len(c)),(60,20,20)); self.assertTrue(no_overlap(a,b,c))
 def test_27_windows(self): self.assertEqual(len(list(windows(list(range(100)),50,10,10))),5)
 def test_27_walkforward(self):
  r=walk_forward(list(range(60)),30,10,lambda train:{'x':1},lambda test,p:{'n':len(test)}); self.assertEqual(len(r),3)
 def test_28_stress(self): self.assertTrue(all(x.passed for x in run_stress_suite(EmergencySafetyLayer())))
 def test_29_forward_gate(self):
  s=ForwardStats(); [s.record_trade(1) for _ in range(100)]; self.assertTrue(DemoForwardGate().ready_for_review(s))
 def test_30_metrics(self):
  m=metrics([2,2,-1,-1],[100,102,101,103,102]); self.assertEqual(m['profit_factor'],2); self.assertGreater(m['max_drawdown_pct'],0)
 def test_30_gate(self):
  g=PerformanceGate(min_trades=4,min_pf=1.2,max_dd=5); self.assertTrue(g.evaluate(metrics([2,2,-1,-1],[100,101,100,102]))['pass'])
 def test_31_refinement(self):
  t=[{'regime':'RANGE','net_pnl':-1} for _ in range(20)]; self.assertIn('disable_or_raise_threshold:RANGE',recommendations(t))
 def test_32_deploy_files(self): self.assertTrue((ROOT/'deploy'/'Dockerfile').exists()); self.assertTrue((ROOT/'deploy'/'docker-compose.yml').exists())
 def test_33_health(self):
  with tempfile.TemporaryDirectory() as d:
   h=HealthState(Path(d)/'h.json'); h.write(status='ok',equity=100); self.assertEqual(h.read()['status'],'ok')
 def test_34_alert_no_destination(self): self.assertEqual(AlertManager().send('x','hello')['reason'],'no_destination')
 def test_35_acceptance_reject_small_sample(self):
  m=metrics([1]*10,[100,101]); self.assertFalse(DemoAcceptanceGate().evaluate(m,private_ws_ok=True,order_reconcile_ok=True,stress_ok=True,days=14)['pass'])
 def test_36_live_lock_default(self):
  os.environ['LIVE_TRADING']='false'; os.environ.pop('LIVE_CONFIRMATION',None); self.assertFalse(live_allowed(acceptance_passed=True))
 def test_37_small_live_locked(self): self.assertFalse(plan(False,True).enabled)
 def test_38_backup(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.txt'; p.write_text('abc'); x=backup_files([str(p)],Path(d)/'b'); self.assertIn('x.txt',x['manifest'])
 def test_39_audit(self): self.assertTrue(audit_tree(ROOT/'src')['pass'])
 def test_40_review_small_sample(self): self.assertEqual(review({'trades':10}).action,'COLLECT_MORE_DATA')

if __name__=='__main__': unittest.main()

class SafetyEquityTests(unittest.TestCase):
 def test_21_zero_demo_equity_blocks_with_explicit_reason(self):
  d=EmergencySafetyLayer().evaluate(now_ms=10,last_market_ms=10,spread_pct=.01,expected_slippage_pct=None,ws_connected=True,account_synced=True,equity_ok=False)
  self.assertFalse(d.allow_new_entries); self.assertIn('no positive demo equity',d.reasons)
