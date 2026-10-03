from __future__ import annotations
from dataclasses import dataclass
from .indicators import EMA, WilderATR, RollingVWAP
from .signals import FamilyScore

@dataclass
class ADX:
    period: int = 14
    prev_h: float | None = None
    prev_l: float | None = None
    prev_c: float | None = None
    atr: float | None = None
    plus_dm: float | None = None
    minus_dm: float | None = None
    adx: float = 0.0

    def update(self, h: float, l: float, c: float) -> tuple[float, float, float]:
        if self.prev_c is None:
            self.prev_h, self.prev_l, self.prev_c = h, l, c
            return 0.0, 0.0, self.adx
        up = h - self.prev_h
        down = self.prev_l - l
        pdm = up if up > down and up > 0 else 0.0
        mdm = down if down > up and down > 0 else 0.0
        tr = max(h-l, abs(h-self.prev_c), abs(l-self.prev_c))
        a = 1.0 / self.period
        self.atr = tr if self.atr is None else a*tr + (1-a)*self.atr
        self.plus_dm = pdm if self.plus_dm is None else a*pdm + (1-a)*self.plus_dm
        self.minus_dm = mdm if self.minus_dm is None else a*mdm + (1-a)*self.minus_dm
        pdi = 100*self.plus_dm/self.atr if self.atr else 0.0
        mdi = 100*self.minus_dm/self.atr if self.atr else 0.0
        den = pdi + mdi
        dx = 100*abs(pdi-mdi)/den if den else 0.0
        self.adx = dx if self.adx == 0 else a*dx + (1-a)*self.adx
        self.prev_h, self.prev_l, self.prev_c = h, l, c
        return pdi, mdi, self.adx

class Supertrend:
    def __init__(self, period=10, multiplier=3.0):
        self.atr = WilderATR(period)
        self.multiplier = multiplier
        self.final_upper = None
        self.final_lower = None
        self.prev_close = None
        self.direction = 0  # +1 bull, -1 bear

    def update(self, h: float, l: float, c: float) -> int:
        a = self.atr.update(h, l, c)
        hl2 = (h+l)/2
        upper = hl2 + self.multiplier*a
        lower = hl2 - self.multiplier*a
        if self.final_upper is None:
            self.final_upper, self.final_lower = upper, lower
            self.direction = 1
        else:
            self.final_upper = upper if upper < self.final_upper or (self.prev_close or c) > self.final_upper else self.final_upper
            self.final_lower = lower if lower > self.final_lower or (self.prev_close or c) < self.final_lower else self.final_lower
            if self.direction >= 0 and c < self.final_lower:
                self.direction = -1
            elif self.direction <= 0 and c > self.final_upper:
                self.direction = 1
        self.prev_close = c
        return self.direction

class TrendFamily:
    def __init__(self):
        self.e9, self.e20, self.e50, self.e200 = EMA(9), EMA(20), EMA(50), EMA(200)
        self.vwap = RollingVWAP(500)
        self.adx = ADX(14)
        self.supertrend = Supertrend(10, 3.0)
        self.last = {}

    def update(self, o: float, h: float, l: float, c: float, v: float) -> FamilyScore:
        e9, e20, e50, e200 = [x.update(c) for x in (self.e9,self.e20,self.e50,self.e200)]
        vw = self.vwap.update(c, v)
        pdi, mdi, adx = self.adx.update(h,l,c)
        st = self.supertrend.update(h,l,c)
        L = S = 0.0
        # EMA structure 40 points
        if e9 > e20: L += 12
        elif e9 < e20: S += 12
        if e20 > e50: L += 12
        elif e20 < e50: S += 12
        if e50 > e200: L += 16
        elif e50 < e200: S += 16
        # Price vs VWAP 15
        if c > vw: L += 15
        elif c < vw: S += 15
        # ADX directional confirmation 25
        strength = min(1.0, max(0.0, (adx-15)/25))
        if pdi > mdi: L += 25*strength
        elif mdi > pdi: S += 25*strength
        # Supertrend 20
        if st > 0: L += 20
        elif st < 0: S += 20
        self.last = {"ema9":e9,"ema20":e20,"ema50":e50,"ema200":e200,"vwap":vw,
                     "plus_di":pdi,"minus_di":mdi,"adx":adx,"supertrend":st}
        return FamilyScore.build("trend", L, S, reason=f"ADX={adx:.1f}, ST={st:+d}")
