from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FamilyScore:
    name: str
    long: float
    short: float
    direction: str
    confidence: float
    veto: bool = False
    reason: str = ""

    @classmethod
    def build(cls, name: str, long: float, short: float, *, veto=False, reason=""):
        long = max(0.0, min(100.0, float(long)))
        short = max(0.0, min(100.0, float(short)))
        if long > short + 5:
            direction = "LONG"
        elif short > long + 5:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"
        confidence = max(long, short)
        return cls(name, long, short, direction, confidence, bool(veto), reason)
