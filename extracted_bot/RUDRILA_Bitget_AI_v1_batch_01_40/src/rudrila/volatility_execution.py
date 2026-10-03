from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
from .indicators import WilderATR
from .signals import FamilyScore

class RollingStats:
    def __init__(self, n=20):
        self.n=n
        self.x=deque(maxlen=n)
    def update(self, v: float):
        self.x.append(float(v))
        m=sum(self.x)/len(self.x)
        var=sum((z-m)**2 for z in self.x)/len(self.x)
        return m, math.sqrt(var)

class VolatilityExecutionFamily:
    def __init__(self, max_spread_pct=0.05):
        self.atr=WilderATR(14)
        self.close_stats=RollingStats(20)
        self.tr_stats=RollingStats(100)
        self.max_spread_pct=max_spread_pct
        self.prev_close=None
        self.last={}

    def update(self, h:float,l:float,c:float, bid:float|None, ask:float|None,
               depth_notional:float|None=None) -> FamilyScore:
        atr=self.atr.update(h,l,c)
        ma,sd=self.close_stats.update(c)
        tr_pct=(h-l)/c*100 if c else 0.0
        tr_mean,tr_sd=self.tr_stats.update(tr_pct)
        bb_width=(4*sd/ma*100) if ma else 0.0
        spread=None
        if bid and ask and bid>0 and ask>=bid:
            spread=(ask-bid)/((ask+bid)/2)*100
        squeeze = bb_width < max(0.08, tr_mean*1.25)
        panic = len(self.tr_stats.x)>=20 and tr_pct > tr_mean + 3*tr_sd
        stale_liquidity = depth_notional is not None and depth_notional < 1000
        # A fast price move is not itself a reason to ban trading.
        # Only genuinely poor execution conditions are hard vetoes.
        veto = bool(
            (spread is not None and spread > self.max_spread_pct)
            or stale_liquidity
        )

        # This family scores execution quality, not price direction.
        # Same quality points are available to LONG and SHORT; veto is independent.
        quality=100.0
        if spread is not None:
            quality -= min(70.0, spread/max(self.max_spread_pct,1e-9)*50)
        if squeeze:
            quality -= 20
        if panic:
            quality -= 60
        if stale_liquidity:
            quality -= 50
        quality=max(0.0,min(100.0,quality))
        self.last={
            "atr":atr,"atr_pct":atr/c*100 if c else 0.0,"bb_width_pct":bb_width,
            "range_pct":tr_pct,"range_mean_pct":tr_mean,"spread_pct":spread,
            "squeeze":squeeze,"panic":panic,"depth_notional":depth_notional,
            "quality":quality
        }
        return FamilyScore.build("volatility_execution",quality,quality,veto=veto,
             reason=f"quality={quality:.1f}, spread={spread}, squeeze={squeeze}, panic={panic}")
