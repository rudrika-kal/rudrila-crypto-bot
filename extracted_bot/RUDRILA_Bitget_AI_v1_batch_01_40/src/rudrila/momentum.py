from __future__ import annotations
from collections import deque
from .indicators import EMA, WilderRSI
from .signals import FamilyScore

class MomentumFamily:
    def __init__(self):
        self.rsi = WilderRSI(14)
        self.fast, self.slow, self.signal = EMA(12), EMA(26), EMA(9)
        self.rsi_window = deque(maxlen=14)
        self.closes = deque(maxlen=11)
        self.last = {}

    def update(self, o: float, h: float, l: float, c: float, v: float) -> FamilyScore:
        r = self.rsi.update(c)
        self.rsi_window.append(r)
        ef, es = self.fast.update(c), self.slow.update(c)
        macd = ef-es
        sig = self.signal.update(macd)
        hist = macd-sig
        self.closes.append(c)
        roc = 0.0 if len(self.closes)<11 else (c/self.closes[0]-1.0)*100
        if len(self.rsi_window) >= 2:
            lo, hi = min(self.rsi_window), max(self.rsi_window)
            stoch_rsi = 50.0 if hi == lo else 100*(r-lo)/(hi-lo)
        else:
            stoch_rsi = 50.0
        rng = max(h-l, 1e-12)
        impulse = (c-o)/rng
        L=S=0.0
        if 52 <= r <= 72: L += 24
        if 28 <= r <= 48: S += 24
        if r > 78: L -= 10
        if r < 22: S -= 10
        if hist > 0: L += 22
        elif hist < 0: S += 22
        if stoch_rsi > 55: L += 16
        elif stoch_rsi < 45: S += 16
        if roc > 0: L += min(20, 6 + abs(roc)*8)
        elif roc < 0: S += min(20, 6 + abs(roc)*8)
        if impulse > .25: L += 18
        elif impulse < -.25: S += 18
        self.last = {"rsi":r,"stoch_rsi":stoch_rsi,"macd_hist":hist,"roc_pct":roc,"impulse":impulse}
        return FamilyScore.build("momentum", L, S,
                                 reason=f"RSI={r:.1f}, StochRSI={stoch_rsi:.1f}, ROC={roc:.3f}%")
