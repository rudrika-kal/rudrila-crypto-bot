from __future__ import annotations
import itertools

def parameter_grid(grid:dict):
    keys=list(grid)
    for vals in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys,vals))

def sweep(grid:dict,evaluator,score_fn=None):
    score_fn=score_fn or (lambda m:m.get('net_pnl',0)-m.get('max_drawdown',0))
    out=[]
    for p in parameter_grid(grid):
        metrics=evaluator(p)
        out.append({'params':p,'metrics':metrics,'objective':score_fn(metrics)})
    return sorted(out,key=lambda x:x['objective'],reverse=True)
