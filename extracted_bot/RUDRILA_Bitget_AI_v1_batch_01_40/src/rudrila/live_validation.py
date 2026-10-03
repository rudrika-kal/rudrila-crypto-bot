from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SmallLivePlan:
    enabled:bool=False
    max_risk_per_trade_pct:float=.10
    max_daily_loss_pct:float=.50
    max_positions:int=1
    required_demo_pass:bool=True

def plan(acceptance_passed:bool,explicit_user_enable:bool)->SmallLivePlan:
    # Returns a plan only. It does not place an order.
    return SmallLivePlan(enabled=bool(acceptance_passed and explicit_user_enable))
