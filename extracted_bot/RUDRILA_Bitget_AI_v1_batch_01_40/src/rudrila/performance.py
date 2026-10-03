from __future__ import annotations
import math

def metrics(pnls:list[float],equity_curve:list[float]|None=None):
    wins=[x for x in pnls if x>0]; losses=[x for x in pnls if x<=0]
    gp=sum(wins); gl=-sum(losses)
    pf=gp/gl if gl>0 else (999.0 if gp>0 else 0.0)
    wr=len(wins)/len(pnls)*100 if pnls else 0.0
    expectancy=sum(pnls)/len(pnls) if pnls else 0.0
    curve=equity_curve or []
    peak=-float('inf'); maxdd=0.0
    for e in curve:
        peak=max(peak,e)
        if peak>0: maxdd=max(maxdd,(peak-e)/peak*100)
    return {'trades':len(pnls),'win_rate':wr,'profit_factor':pf,'expectancy':expectancy,
            'net_pnl':sum(pnls),'max_drawdown_pct':maxdd,'avg_win':sum(wins)/len(wins) if wins else 0,
            'avg_loss':sum(losses)/len(losses) if losses else 0}

class PerformanceGate:
    def __init__(self,min_trades=100,min_pf=1.20,max_dd=5.0,min_expectancy=0.0):
        self.min_trades=min_trades; self.min_pf=min_pf; self.max_dd=max_dd; self.min_expectancy=min_expectancy
    def evaluate(self,m:dict):
        checks={
          'sample_size':m.get('trades',0)>=self.min_trades,
          'profit_factor':m.get('profit_factor',0)>=self.min_pf,
          'drawdown':m.get('max_drawdown_pct',999)<=self.max_dd,
          'expectancy':m.get('expectancy',-999)>self.min_expectancy,
        }
        return {'pass':all(checks.values()),'checks':checks}
