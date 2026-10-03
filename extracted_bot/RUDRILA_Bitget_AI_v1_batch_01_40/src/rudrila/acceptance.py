from __future__ import annotations
from .performance import PerformanceGate

class DemoAcceptanceGate:
    def __init__(self): self.performance=PerformanceGate(min_trades=100,min_pf=1.2,max_dd=5,min_expectancy=0)
    def evaluate(self,metrics:dict,*,private_ws_ok:bool,order_reconcile_ok:bool,stress_ok:bool,days:int):
        p=self.performance.evaluate(metrics)
        checks={**p['checks'],'private_ws':private_ws_ok,'order_reconcile':order_reconcile_ok,
                'stress_suite':stress_ok,'forward_days':days>=14}
        return {'pass':all(checks.values()),'checks':checks}
