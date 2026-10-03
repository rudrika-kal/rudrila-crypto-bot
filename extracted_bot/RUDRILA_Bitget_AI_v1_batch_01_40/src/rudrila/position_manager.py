from __future__ import annotations
from dataclasses import dataclass, replace

@dataclass
class ManagedPosition:
    symbol:str
    side:str
    qty:float
    entry:float
    stop:float
    tp1:float
    tp2:float
    initial_r:float
    opened_ms:int
    partial_taken:bool=False
    breakeven_moved:bool=False
    trailing:bool=False

@dataclass(frozen=True)
class PositionAction:
    action:str
    price:float|None
    qty_fraction:float
    reason:str

class PositionManager:
    def __init__(self,be_trigger_r=.8,trail_trigger_r=1.2,max_hold_ms=45*60*1000):
        self.be_trigger_r=be_trigger_r
        self.trail_trigger_r=trail_trigger_r
        self.max_hold_ms=max_hold_ms

    def favorable_r(self,p:ManagedPosition,mark:float)->float:
        move=(mark-p.entry) if p.side=="LONG" else (p.entry-mark)
        return move/max(p.initial_r,1e-12)

    def update(self,p:ManagedPosition,mark:float,now_ms:int,atr:float,
               reversal_score:float=0.0)->PositionAction:
        # Hard exits first.
        if p.side=="LONG":
            if mark<=p.stop: return PositionAction("CLOSE",mark,1.0,"STOP")
            if mark>=p.tp2: return PositionAction("CLOSE",mark,1.0,"TP2")
        else:
            if mark>=p.stop: return PositionAction("CLOSE",mark,1.0,"STOP")
            if mark<=p.tp2: return PositionAction("CLOSE",mark,1.0,"TP2")
        if now_ms-p.opened_ms>=self.max_hold_ms:
            return PositionAction("CLOSE",mark,1.0,"TIME_EXIT")
        if reversal_score>=88:
            return PositionAction("CLOSE",mark,1.0,"STRONG_REVERSAL")

        r=self.favorable_r(p,mark)
        if not p.partial_taken:
            hit_tp1 = mark>=p.tp1 if p.side=="LONG" else mark<=p.tp1
            if hit_tp1:
                p.partial_taken=True
                return PositionAction("PARTIAL_CLOSE",mark,.5,"TP1")
        if r>=self.be_trigger_r and not p.breakeven_moved:
            p.stop=p.entry
            p.breakeven_moved=True
            return PositionAction("MOVE_STOP",p.stop,0.0,"BREAKEVEN")
        if r>=self.trail_trigger_r:
            p.trailing=True
            candidate=mark-atr*.8 if p.side=="LONG" else mark+atr*.8
            old=p.stop
            p.stop=max(p.stop,candidate) if p.side=="LONG" else min(p.stop,candidate)
            if p.stop!=old:
                return PositionAction("MOVE_STOP",p.stop,0.0,"ATR_TRAIL")
        return PositionAction("HOLD",None,0.0,"no exit condition")
