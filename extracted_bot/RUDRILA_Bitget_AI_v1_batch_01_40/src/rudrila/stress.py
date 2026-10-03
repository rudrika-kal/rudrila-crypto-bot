from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class StressResult:
    name:str; passed:bool; detail:str

def run_stress_suite(safety_layer, order_executor=None):
    out=[]
    d=safety_layer.evaluate(now_ms=10000,last_market_ms=1,spread_pct=.001,expected_slippage_pct=.01,ws_connected=True,account_synced=True)
    out.append(StressResult('stale_feed',not d.allow_new_entries,'blocked' if not d.allow_new_entries else 'FAILED'))
    d=safety_layer.evaluate(now_ms=10000,last_market_ms=10000,spread_pct=.5,expected_slippage_pct=.01,ws_connected=True,account_synced=True)
    out.append(StressResult('wide_spread',not d.allow_new_entries,'blocked' if not d.allow_new_entries else 'FAILED'))
    d=safety_layer.evaluate(now_ms=10000,last_market_ms=10000,spread_pct=.001,expected_slippage_pct=.01,ws_connected=False,account_synced=True)
    out.append(StressResult('ws_disconnect',not d.allow_new_entries,'blocked' if not d.allow_new_entries else 'FAILED'))
    d=safety_layer.evaluate(now_ms=10000,last_market_ms=10000,spread_pct=.001,expected_slippage_pct=.01,ws_connected=True,account_synced=False)
    out.append(StressResult('account_desync',not d.allow_new_entries,'blocked' if not d.allow_new_entries else 'FAILED'))
    return out
