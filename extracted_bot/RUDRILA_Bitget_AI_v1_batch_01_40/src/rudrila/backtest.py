from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from .accounting import AccountingEngine, TradeLedger

@dataclass(frozen=True)
class Bar:
    ts:int; open:float; high:float; low:float; close:float; volume:float

@dataclass(frozen=True)
class Signal:
    side:str='NONE'; stop:float|None=None; tp:float|None=None; score:float=0.0

@dataclass
class BacktestResult:
    trades:list
    equity_curve:list
    starting_equity:float
    ending_equity:float

class Backtester:
    """Close-of-bar signal -> next-bar-open fill. No signal can fill on its own candle."""
    def __init__(self, starting_equity=1000.0, risk_pct=.25, accounting=None):
        self.starting_equity=starting_equity; self.risk_pct=risk_pct
        self.acct=accounting or AccountingEngine()

    def run(self,bars:list[Bar], strategy:Callable[[list[Bar],float],Signal])->BacktestResult:
        if len(bars)<3: return BacktestResult([],[(bars[0].ts,self.starting_equity)] if bars else [],self.starting_equity,self.starting_equity)
        eq=self.starting_equity; curve=[(bars[0].ts,eq)]; trades=[]; pending=None; pos=None
        for i,bar in enumerate(bars):
            # Fill prior close's signal at this bar's open.
            if pending and not pos:
                sig=pending; pending=None
                if sig.side in ('LONG','SHORT') and sig.stop and sig.tp:
                    dist=abs(bar.open-sig.stop)
                    if dist>0:
                        qty=min((eq*self.risk_pct/100)/dist,(eq*.25)/bar.open)
                        entry,cost=self.acct.fill(sig.side,bar.open,qty,opening=True)
                        pos={'side':sig.side,'qty':qty,'entry_ref':bar.open,'entry':entry,'entry_fee':cost.fee,
                             'stop':sig.stop,'tp':sig.tp,'opened':bar.ts,'score':sig.score}
            if pos:
                exit_ref=reason=None
                if pos['side']=='LONG':
                    stop_hit=bar.low<=pos['stop']; tp_hit=bar.high>=pos['tp']
                else:
                    stop_hit=bar.high>=pos['stop']; tp_hit=bar.low<=pos['tp']
                # Conservative same-bar ambiguity: stop first.
                if stop_hit: exit_ref=pos['stop']; reason='STOP'
                elif tp_hit: exit_ref=pos['tp']; reason='TP'
                if exit_ref is not None:
                    ex,cost=self.acct.fill(pos['side'],exit_ref,pos['qty'],opening=False)
                    led=TradeLedger(pos['side'],pos['qty'],pos['entry_ref'],pos['entry'],pos['entry_fee'],exit_ref,ex,cost.fee)
                    pnl=led.net_pnl(); eq+=pnl
                    trades.append({'side':pos['side'],'opened':pos['opened'],'closed':bar.ts,'entry':pos['entry'],'exit':ex,
                                   'qty':pos['qty'],'gross':led.gross_pnl(),'net':pnl,'reason':reason,'score':pos['score']})
                    pos=None
            # Signal only after current bar is fully known; next iteration executes it.
            if not pos and i < len(bars)-1:
                pending=strategy(bars[:i+1],eq)
            curve.append((bar.ts,eq))
        return BacktestResult(trades,curve,self.starting_equity,eq)
