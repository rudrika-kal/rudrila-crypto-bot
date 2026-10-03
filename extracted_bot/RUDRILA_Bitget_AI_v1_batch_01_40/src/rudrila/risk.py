from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RiskDecision:
    allow: bool
    qty: float
    risk_usdt: float
    reason: str

class RiskEngine:
    def __init__(self,risk_per_trade_pct=.25,max_daily_loss_pct=1.5,
                 max_drawdown_pct=5.0,max_positions=2,max_correlated_same_side=1):
        self.risk_per_trade_pct=risk_per_trade_pct
        self.max_daily_loss_pct=max_daily_loss_pct
        self.max_drawdown_pct=max_drawdown_pct
        self.max_positions=max_positions
        self.max_correlated_same_side=max_correlated_same_side

    def assess(self,equity:float,day_start:float,equity_peak:float,entry:float,stop:float,
               side:str,positions:list[dict],min_notional=5.0)->RiskDecision:
        if equity<=0 or entry<=0 or stop<=0 or entry==stop:
            return RiskDecision(False,0,0,"invalid account/price")
        dl=max(0,(day_start-equity)/day_start*100) if day_start else 100
        dd=max(0,(equity_peak-equity)/equity_peak*100) if equity_peak else 100
        if dl>=self.max_daily_loss_pct:
            return RiskDecision(False,0,0,f"daily loss cap {dl:.2f}%")
        if dd>=self.max_drawdown_pct:
            return RiskDecision(False,0,0,f"drawdown cap {dd:.2f}%")
        if len(positions)>=self.max_positions:
            return RiskDecision(False,0,0,"max positions")
        same=sum(1 for p in positions if p.get("side")==side and p.get("symbol") in ("BTCUSDT","ETHUSDT"))
        if same>=self.max_correlated_same_side:
            return RiskDecision(False,0,0,"correlated same-side exposure")
        risk=equity*self.risk_per_trade_pct/100
        dist=abs(entry-stop)
        qty=risk/dist
        # Cap notional at 25% equity for this initial demo model.
        qty=min(qty,(equity*.25)/entry)
        if qty*entry<min_notional:
            return RiskDecision(False,0,risk,"below minimum notional")
        return RiskDecision(True,qty,risk,"risk approved")
