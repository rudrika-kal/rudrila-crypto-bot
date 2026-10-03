from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque

@dataclass(frozen=True)
class SafetyDecision:
    allow_new_entries: bool
    emergency: bool
    reasons: tuple[str, ...]

class EmergencySafetyLayer:
    """Hard-veto layer. Never creates a trade; it can only block new entries."""
    def __init__(self, max_spread_pct=.05, stale_ms=3000, max_slippage_pct=.08,
                 max_api_errors=3, max_rejects=3):
        self.max_spread_pct=max_spread_pct
        self.stale_ms=stale_ms
        self.max_slippage_pct=max_slippage_pct
        self.max_api_errors=max_api_errors
        self.max_rejects=max_rejects
        self.api_errors=0
        self.order_rejects=0
        self.manual_kill=False
        self.events=deque(maxlen=200)

    def record_api_error(self, detail=''):
        self.api_errors += 1
        self.events.append(('api_error', detail))

    def record_api_success(self):
        self.api_errors = 0

    def record_order_reject(self, detail=''):
        self.order_rejects += 1
        self.events.append(('order_reject', detail))

    def clear_order_rejects(self):
        self.order_rejects=0

    def evaluate(self, *, now_ms:int, last_market_ms:int, spread_pct:float|None,
                 expected_slippage_pct:float|None, ws_connected:bool,
                 account_synced:bool, duplicate_order:bool=False, equity_ok:bool=True,
                 daily_loss_hit:bool=False, drawdown_hit:bool=False)->SafetyDecision:
        reasons=[]
        if self.manual_kill: reasons.append('manual kill switch')
        if not ws_connected: reasons.append('websocket disconnected')
        if not account_synced: reasons.append('account/order state desynced')
        if not equity_ok: reasons.append('no positive demo equity')
        if not last_market_ms or now_ms-last_market_ms>self.stale_ms: reasons.append('stale market data')
        if spread_pct is not None and spread_pct>self.max_spread_pct: reasons.append('spread too wide')
        if expected_slippage_pct is not None and expected_slippage_pct>self.max_slippage_pct: reasons.append('slippage too high')
        if duplicate_order: reasons.append('duplicate order risk')
        if self.api_errors>=self.max_api_errors: reasons.append('repeated API errors')
        if self.order_rejects>=self.max_rejects: reasons.append('repeated order rejects')
        if daily_loss_hit: reasons.append('daily loss cap')
        if drawdown_hit: reasons.append('drawdown cap')
        return SafetyDecision(not reasons, bool(reasons), tuple(reasons))
