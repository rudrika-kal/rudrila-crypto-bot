from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FillCost:
    notional: float
    fee: float
    slippage_cost: float

@dataclass
class TradeLedger:
    side: str
    qty: float
    entry_reference: float
    entry_fill: float
    entry_fee: float
    exit_reference: float|None=None
    exit_fill: float|None=None
    exit_fee: float=0.0
    funding: float=0.0
    other_cost: float=0.0

    def gross_pnl(self)->float:
        if self.exit_fill is None: return 0.0
        move=(self.exit_fill-self.entry_fill) if self.side=='LONG' else (self.entry_fill-self.exit_fill)
        return self.qty*move

    def net_pnl(self)->float:
        return self.gross_pnl()-self.entry_fee-self.exit_fee+self.funding-self.other_cost

    def total_costs(self)->float:
        slip=abs(self.entry_fill-self.entry_reference)*self.qty
        if self.exit_reference is not None and self.exit_fill is not None:
            slip += abs(self.exit_fill-self.exit_reference)*self.qty
        return self.entry_fee+self.exit_fee+slip+self.other_cost-self.funding

class AccountingEngine:
    def __init__(self, taker_fee_pct=.06, maker_fee_pct=.02, slippage_pct=.02):
        self.taker_fee_pct=taker_fee_pct
        self.maker_fee_pct=maker_fee_pct
        self.slippage_pct=slippage_pct

    def fill(self, side:str, reference:float, qty:float, *, opening:bool, maker=False)->tuple[float, FillCost]:
        s=self.slippage_pct/100
        # buy pays above reference; sell receives below reference
        trade_side = 'buy' if (opening and side=='LONG') or ((not opening) and side=='SHORT') else 'sell'
        fill=reference*(1+s) if trade_side=='buy' else reference*(1-s)
        fee_pct=self.maker_fee_pct if maker else self.taker_fee_pct
        fee=qty*fill*fee_pct/100
        return fill, FillCost(qty*fill, fee, abs(fill-reference)*qty)
