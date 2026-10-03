from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ReviewDecision:
    action:str; reason:str

def review(current:dict,previous:dict|None=None)->ReviewDecision:
    if current.get('trades',0)<100: return ReviewDecision('COLLECT_MORE_DATA','sample below 100 closed trades')
    if current.get('profit_factor',0)<1: return ReviewDecision('INVESTIGATE','profit factor below 1')
    if current.get('max_drawdown_pct',999)>5: return ReviewDecision('REDUCE_RISK_OR_DISABLE','drawdown above limit')
    if previous and current.get('profit_factor',0)<previous.get('profit_factor',0)*.8:
        return ReviewDecision('REGRESSION_REVIEW','profit factor deteriorated >20%')
    return ReviewDecision('NO_RANDOM_CHANGE','no evidence-based parameter change required')
