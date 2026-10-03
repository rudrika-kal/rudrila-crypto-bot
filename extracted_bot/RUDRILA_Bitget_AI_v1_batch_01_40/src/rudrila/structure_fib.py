from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from .signals import FamilyScore

@dataclass(frozen=True)
class FibMap:
    direction: str
    swing_low: float
    swing_high: float
    levels: dict[str,float]
    extensions: dict[str,float]

class StructureFibFamily:
    def __init__(self, lookback=55):
        self.rows = deque(maxlen=max(lookback+10, 100))
        self.lookback = lookback
        self.last_map: FibMap | None = None
        self.last = {}

    @staticmethod
    def fibonacci(low: float, high: float, direction: str) -> FibMap:
        r = max(high-low, 1e-12)
        if direction == "UP":
            levels = {k: high-r*x for k,x in {
                "23.6":.236,"38.2":.382,"50.0":.5,"61.8":.618,"78.6":.786}.items()}
            ext = {"127.2": high+r*.272, "161.8": high+r*.618}
        else:
            levels = {k: low+r*x for k,x in {
                "23.6":.236,"38.2":.382,"50.0":.5,"61.8":.618,"78.6":.786}.items()}
            ext = {"127.2": low-r*.272, "161.8": low-r*.618}
        return FibMap(direction, low, high, levels, ext)

    def update(self, o: float, h: float, l: float, c: float, v: float, atr: float | None=None) -> FamilyScore:
        self.rows.append({"o":o,"h":h,"l":l,"c":c,"v":v})
        if len(self.rows) < 12:
            return FamilyScore.build("structure_fibonacci", 0, 0, reason="warming up")
        rows = list(self.rows)[-self.lookback:]
        hi = max(r["h"] for r in rows)
        lo = min(r["l"] for r in rows)
        hi_i = max(i for i,r in enumerate(rows) if r["h"] == hi)
        lo_i = max(i for i,r in enumerate(rows) if r["l"] == lo)
        direction = "UP" if lo_i < hi_i else "DOWN"
        fmap = self.fibonacci(lo, hi, direction)
        self.last_map = fmap
        prior = rows[:-1]
        prior_hi = max(r["h"] for r in prior)
        prior_lo = min(r["l"] for r in prior)
        tol = max((atr or 0.0)*0.35, c*0.0007)
        L=S=0.0
        breakout_up = c > prior_hi
        breakout_dn = c < prior_lo
        if breakout_up: L += 35
        if breakout_dn: S += 35

        # Golden pocket: 50%-61.8% retracement with rejection in swing direction.
        p50, p618 = fmap.levels["50.0"], fmap.levels["61.8"]
        zlo, zhi = sorted((p50,p618))
        in_golden = (l <= zhi+tol and h >= zlo-tol)
        bullish_reject = c > o and c >= (h+l)/2
        bearish_reject = c < o and c <= (h+l)/2
        if direction == "UP":
            L += 20
            if in_golden and bullish_reject: L += 35
            if c < fmap.levels["78.6"]-tol: S += 20
        else:
            S += 20
            if in_golden and bearish_reject: S += 35
            if c > fmap.levels["78.6"]+tol: L += 20

        # Retest of prior breakout level.
        if abs(c-prior_hi) <= tol and c >= prior_hi and bullish_reject: L += 10
        if abs(c-prior_lo) <= tol and c <= prior_lo and bearish_reject: S += 10

        self.last = {
            "direction":direction,"swing_low":lo,"swing_high":hi,"golden_zone":[zlo,zhi],
            "in_golden":in_golden,"breakout_up":breakout_up,"breakout_down":breakout_dn,
            "levels":fmap.levels,"extensions":fmap.extensions
        }
        return FamilyScore.build("structure_fibonacci", L, S,
                                 reason=f"{direction} swing {lo:.4f}-{hi:.4f}, golden={in_golden}")
