from __future__ import annotations
from dataclasses import dataclass,field

@dataclass
class ForwardStats:
    decisions:int=0; entries:int=0; closed:int=0; wins:int=0; net_pnl:float=0.0
    errors:int=0; rejects:int=0
    samples:list=field(default_factory=list)
    def record_trade(self,pnl:float):
        self.closed+=1; self.net_pnl+=pnl; self.wins+=int(pnl>0); self.samples.append(pnl)
    @property
    def win_rate(self): return self.wins/self.closed*100 if self.closed else 0.0

class DemoForwardGate:
    def __init__(self,min_closed=100): self.min_closed=min_closed
    def ready_for_review(self,s:ForwardStats):
        return s.closed>=self.min_closed and s.errors==0
