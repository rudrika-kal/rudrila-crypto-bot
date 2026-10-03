from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ExitPlan:
    stop: float
    tp1: float
    tp2: float
    risk_distance: float
    rr1: float
    rr2: float
    basis: str

class ExitPlanner:
    def __init__(self,min_stop_pct=.25,atr_mult=1.1,rr1=1.35,rr2=1.8):
        self.min_stop_pct=min_stop_pct
        self.atr_mult=atr_mult
        self.rr1=rr1
        self.rr2=rr2

    def plan(self,side:str,entry:float,atr:float,swing_low:float|None=None,
             swing_high:float|None=None,fib_extension:float|None=None)->ExitPlan:
        min_dist=entry*self.min_stop_pct/100
        atr_dist=max(min_dist,atr*self.atr_mult)
        if side=="LONG":
            structural=(entry-swing_low) if swing_low and swing_low<entry else 0
            dist=max(atr_dist,structural)
            stop=entry-dist
            tp1=entry+dist*self.rr1
            tp2=entry+dist*self.rr2
            if fib_extension and fib_extension>entry:
                tp2=max(tp2,fib_extension)
        elif side=="SHORT":
            structural=(swing_high-entry) if swing_high and swing_high>entry else 0
            dist=max(atr_dist,structural)
            stop=entry+dist
            tp1=entry-dist*self.rr1
            tp2=entry-dist*self.rr2
            if fib_extension and fib_extension<entry:
                tp2=min(tp2,fib_extension)
        else:
            raise ValueError("side must be LONG or SHORT")
        return ExitPlan(stop,tp1,tp2,dist,self.rr1,self.rr2,"ATR+structure+Fib")
