from __future__ import annotations
from collections import deque
from .signals import FamilyScore

class VolumeDerivativesFamily:
    def __init__(self):
        self.vols=deque(maxlen=20)
        self.prev_close=None
        self.obv=0.0
        self.prev_oi=None
        self.last={}

    def update(self, close: float, volume: float, funding_rate: float|None=None,
               open_interest: float|None=None) -> FamilyScore:
        avg=sum(self.vols)/len(self.vols) if self.vols else volume
        rel=volume/avg if avg>0 else 1.0
        self.vols.append(volume)
        price_delta=0.0 if self.prev_close in (None,0) else close/self.prev_close-1
        if self.prev_close is not None:
            if close>self.prev_close: self.obv += volume
            elif close<self.prev_close: self.obv -= volume
        oi_delta=0.0
        if open_interest is not None and self.prev_oi not in (None,0):
            oi_delta=open_interest/self.prev_oi-1
        if open_interest is not None:
            self.prev_oi=open_interest
        self.prev_close=close

        L=S=0.0
        # Relative volume validates price direction.
        vol_power=min(30.0, max(0.0,(rel-0.8)*30))
        if price_delta>0: L += vol_power
        elif price_delta<0: S += vol_power
        # OI expansion with price direction is participation confirmation.
        if oi_delta>0.0002:
            if price_delta>0: L += min(35, 12+oi_delta*5000)
            elif price_delta<0: S += min(35, 12+oi_delta*5000)
        elif oi_delta < -0.0005:
            # Position unwinding = lower conviction for current direction.
            if price_delta>0: L = max(0,L-8)
            elif price_delta<0: S = max(0,S-8)

        # Funding is a crowding context, not a direction trigger.
        if funding_rate is not None:
            if funding_rate > 0.0008:
                L=max(0,L-12); S+=8
            elif funding_rate < -0.0008:
                S=max(0,S-12); L+=8

        # OBV direction (small weight)
        if self.obv>0: L+=15
        elif self.obv<0: S+=15
        self.last={"relative_volume":rel,"obv":self.obv,"price_delta":price_delta,
                   "funding_rate":funding_rate,"open_interest":open_interest,"oi_delta":oi_delta}
        return FamilyScore.build("volume_derivatives",L,S,
            reason=f"RVOL={rel:.2f}, OIΔ={oi_delta*100:.3f}%, funding={funding_rate}")
