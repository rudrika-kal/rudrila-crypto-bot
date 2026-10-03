from __future__ import annotations
from dataclasses import dataclass
from .signals import FamilyScore

WEIGHTS={
 "order_flow":20,
 "structure_fibonacci":18,
 "trend":15,
 "news_macro":15,
 "momentum":12,
 "volume_derivatives":12,
 "volatility_execution":8,
}

@dataclass(frozen=True)
class ConsensusResult:
    long_score: float
    short_score: float
    direction: str
    aligned_families: int
    veto: bool
    reasons: list[str]

def consensus(scores:dict[str,FamilyScore])->ConsensusResult:
    missing=set(WEIGHTS)-set(scores)
    if missing:
        raise ValueError(f"missing families: {sorted(missing)}")
    L=S=0.0
    reasons=[]
    long_aligned=short_aligned=0
    veto=False
    for name,w in WEIGHTS.items():
        s=scores[name]
        veto = veto or s.veto
        L += w*(s.long/100)
        S += w*(s.short/100)
        if name != "volatility_execution":
            if s.direction=="LONG": long_aligned+=1
            elif s.direction=="SHORT": short_aligned+=1
        reasons.append(f"{name}:{s.direction}:{s.confidence:.1f}")
    if L>S+3:
        d="LONG"; aligned=long_aligned
    elif S>L+3:
        d="SHORT"; aligned=short_aligned
    else:
        d="NEUTRAL"; aligned=max(long_aligned,short_aligned)
    return ConsensusResult(round(L,3),round(S,3),d,aligned,veto,reasons)
