from __future__ import annotations
from collections import deque
import math

class RegimeDetector:
    def __init__(self):
        self.returns=deque(maxlen=100)
        self.atrp=deque(maxlen=100)
        self.prev=None
        self.last={}
    def update(self, close:float, atr:float, adx:float, spread_pct:float|None,
               bb_width_pct:float, breakout:bool=False, depth_notional:float|None=None)->str:
        if self.prev:
            self.returns.append((close/self.prev-1)*100)
        self.prev=close
        atr_pct=atr/close*100 if close else 0
        self.atrp.append(atr_pct)
        med=sorted(self.atrp)[len(self.atrp)//2] if self.atrp else atr_pct
        shock=abs(self.returns[-1]) if self.returns else 0
        bad_spread = spread_pct is not None and spread_pct>0.05
        shallow = depth_notional is not None and depth_notional<1000
        spread_plus_thin = bad_spread and (depth_notional is None or depth_notional<50000)
        if shallow or spread_plus_thin:
            r="LOW_LIQUIDITY"
        elif shock > max(0.8, med*4) or atr_pct > max(1.5, med*3):
            r="PANIC"
        elif breakout and adx>=22:
            r="BREAKOUT"
        elif adx>=24:
            r="TREND"
        elif bb_width_pct < max(0.15,med*2):
            r="RANGE"
        else:
            r="NORMAL"
        self.last={"regime":r,"atr_pct":atr_pct,"median_atr_pct":med,
                   "shock_return_pct":shock,"adx":adx,"bb_width_pct":bb_width_pct,
                   "spread_pct":spread_pct,"depth_notional":depth_notional}
        return r
