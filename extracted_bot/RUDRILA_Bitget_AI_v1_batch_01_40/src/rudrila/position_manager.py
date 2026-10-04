from __future__ import annotations
from dataclasses import dataclass

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
    peak_r:float=0.0
    entry_regime:str=''

@dataclass(frozen=True)
class PositionAction:
    action:str
    price:float|None
    qty_fraction:float
    reason:str

class PositionManager:
    """Signal-aware, conservative position management for Demo futures.

    A single 1m reversal never closes a trade by itself. Dynamic exits require
    higher-timeframe confirmation, strong opposite consensus, a failed breakout,
    profit giveback, a time stop, or the account kill switch.
    """
    def __init__(self,be_trigger_r=.8,trail_trigger_r=1.2,max_hold_ms=45*60*1000,
                 opposite_score=60.0,opposite_aligned=4,
                 false_breakout_ms=10*60*1000,false_breakout_adverse_r=.25,
                 profit_lock_trigger_r=.90,profit_lock_floor_r=.25,
                 trailing_giveback_r=.45):
        self.be_trigger_r=float(be_trigger_r)
        self.trail_trigger_r=float(trail_trigger_r)
        self.max_hold_ms=int(max_hold_ms)
        self.opposite_score=float(opposite_score)
        self.opposite_aligned=int(opposite_aligned)
        self.false_breakout_ms=int(false_breakout_ms)
        self.false_breakout_adverse_r=float(false_breakout_adverse_r)
        self.profit_lock_trigger_r=float(profit_lock_trigger_r)
        self.profit_lock_floor_r=float(profit_lock_floor_r)
        self.trailing_giveback_r=float(trailing_giveback_r)

    def favorable_r(self,p:ManagedPosition,mark:float)->float:
        move=(mark-p.entry) if p.side=="LONG" else (p.entry-mark)
        return move/max(p.initial_r,1e-12)

    def update(self,p:ManagedPosition,mark:float,now_ms:int,atr:float,
               reversal_score:float=0.0, *, consensus_direction:str='NEUTRAL',
               long_score:float=0.0, short_score:float=0.0,
               aligned_families:int=0, mtf1:str='NEUTRAL',
               mtf5:str='NEUTRAL', mtf15:str='NEUTRAL',
               structure_direction:str='NEUTRAL',
               momentum_direction:str='NEUTRAL',
               kill_switch:bool=False)->PositionAction:
        side=str(p.side or '').upper()
        if side not in ('LONG','SHORT') or p.entry<=0 or mark<=0:
            return PositionAction("HOLD",None,0.0,"invalid position metadata")

        # Existing exchange hard exits remain the first line of defense.
        if side=="LONG":
            if mark<=p.stop: return PositionAction("CLOSE",mark,1.0,"STOP")
            if mark>=p.tp2: return PositionAction("CLOSE",mark,1.0,"TP2")
        else:
            if mark>=p.stop: return PositionAction("CLOSE",mark,1.0,"STOP")
            if mark<=p.tp2: return PositionAction("CLOSE",mark,1.0,"TP2")

        if kill_switch:
            return PositionAction("CLOSE",mark,1.0,"ACCOUNT_KILL_SWITCH")

        r=self.favorable_r(p,mark)
        p.peak_r=max(float(p.peak_r or 0.0),r)
        age=max(0,int(now_ms)-int(p.opened_ms or now_ms))
        opp='SHORT' if side=='LONG' else 'LONG'
        opp_score=float(short_score if opp=='SHORT' else long_score)

        # Both higher timeframes flipping is strong enough to invalidate the trade.
        if mtf5==opp and mtf15==opp:
            return PositionAction("CLOSE",mark,1.0,"MTF_5M_15M_REVERSAL")

        # Strong opposite consensus needs 4+ aligned families and an extra
        # confirmation. This avoids closing on a noisy one-minute flip.
        extra_confirm=(mtf5==opp or
                       (structure_direction==opp and momentum_direction==opp))
        if (consensus_direction==opp and opp_score>=self.opposite_score
                and int(aligned_families)>=self.opposite_aligned and extra_confirm):
            return PositionAction("CLOSE",mark,1.0,
                                  f"STRONG_OPPOSITE_{opp}_{opp_score:.1f}")

        # A fresh BREAKOUT entry that immediately moves >=0.25R against us and
        # loses momentum plus 1m/structure confirmation is treated as failed.
        if str(p.entry_regime).upper()=='BREAKOUT' and age<=self.false_breakout_ms:
            failed=(r<=-self.false_breakout_adverse_r
                    and momentum_direction==opp
                    and (mtf1==opp or structure_direction==opp))
            if failed:
                return PositionAction("CLOSE",mark,1.0,"FALSE_BREAKOUT")

        # Lock profits by exiting on a material giveback; this is execution-safe
        # and does not depend on exchange stop-modification support.
        if (p.peak_r>=self.trail_trigger_r and r>0
                and p.peak_r-r>=self.trailing_giveback_r):
            return PositionAction("CLOSE",mark,1.0,
                                  f"TRAIL_GIVEBACK_FROM_{p.peak_r:.2f}R")
        if p.peak_r>=self.profit_lock_trigger_r and 0<r<=self.profit_lock_floor_r:
            return PositionAction("CLOSE",mark,1.0,
                                  f"PROFIT_LOCK_FROM_{p.peak_r:.2f}R")

        # Legacy strong reversal hook stays available for callers.
        if reversal_score>=88:
            return PositionAction("CLOSE",mark,1.0,"STRONG_REVERSAL")

        # Fast-scalp time stop: do not let an unproductive position linger.
        if age>=self.max_hold_ms:
            return PositionAction("CLOSE",mark,1.0,"TIME_EXIT_45M")

        # Existing staged management remains available. Runtime currently uses
        # CLOSE actions directly; exchange TP/SL still protects the position.
        if not p.partial_taken:
            hit_tp1 = mark>=p.tp1 if side=="LONG" else mark<=p.tp1
            if hit_tp1:
                p.partial_taken=True
                return PositionAction("PARTIAL_CLOSE",mark,.5,"TP1")
        if r>=self.be_trigger_r and not p.breakeven_moved:
            p.stop=p.entry
            p.breakeven_moved=True
            return PositionAction("MOVE_STOP",p.stop,0.0,"BREAKEVEN")
        if r>=self.trail_trigger_r:
            p.trailing=True
            candidate=mark-atr*.8 if side=="LONG" else mark+atr*.8
            old=p.stop
            p.stop=max(p.stop,candidate) if side=="LONG" else min(p.stop,candidate)
            if p.stop!=old:
                return PositionAction("MOVE_STOP",p.stop,0.0,"ATR_TRAIL")
        return PositionAction("HOLD",None,0.0,"no exit condition")
