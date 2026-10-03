from __future__ import annotations
from collections import defaultdict

def by_regime(trades:list[dict]):
    g=defaultdict(list)
    for t in trades: g[t.get('regime','UNKNOWN')].append(float(t.get('net_pnl',0)))
    return {k:{'n':len(v),'net':sum(v),'avg':sum(v)/len(v)} for k,v in g.items()}

def recommendations(trades:list[dict])->list[str]:
    out=[]
    for regime,m in by_regime(trades).items():
        if m['n']>=20 and m['avg']<0: out.append(f'disable_or_raise_threshold:{regime}')
    if not out: out.append('no_evidence_based_change')
    return out
