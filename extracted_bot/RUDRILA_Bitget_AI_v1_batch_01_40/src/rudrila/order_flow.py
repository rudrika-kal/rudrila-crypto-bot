from __future__ import annotations
from .signals import FamilyScore

def _levels(book: dict | None, key_short: str, key_long: str):
    if not book:
        return []
    x = book.get(key_short)
    if x is None:
        x = book.get(key_long, [])
    return x or []

def _trade_parts(t):
    if isinstance(t, dict):
        price = t.get("price") or t.get("px") or t.get("p")
        size = t.get("size") or t.get("qty") or t.get("q")
        side = t.get("side") or t.get("direction")
        return price, size, side
    if isinstance(t, (list,tuple)) and len(t) >= 4:
        # Flexible fallback for exchange array formats: [ts, price, size, side, ...]
        return t[1], t[2], t[3]
    return None, None, None

class OrderFlowFamily:
    def __init__(self, max_spread_pct=0.05):
        self.max_spread_pct = max_spread_pct
        self.last = {}

    def score(self, book: dict | None, trades, bid: float|None=None, ask: float|None=None) -> FamilyScore:
        bids = _levels(book, "b", "bids")
        asks = _levels(book, "a", "asks")
        b_notional=a_notional=0.0
        for i,row in enumerate(bids[:5]):
            if len(row) >= 2:
                p,q=float(row[0]),float(row[1]); b_notional += p*q/(1+i*.35)
        for i,row in enumerate(asks[:5]):
            if len(row) >= 2:
                p,q=float(row[0]),float(row[1]); a_notional += p*q/(1+i*.35)
        den=b_notional+a_notional
        book_imb=(b_notional-a_notional)/den if den else 0.0

        buy=sell=0.0
        for t in list(trades)[-200:]:
            p,q,side=_trade_parts(t)
            if p is None or q is None or side is None: continue
            n=float(p)*float(q)
            s=str(side).lower()
            if s in ("buy","b","1","long"): buy += n
            elif s in ("sell","s","2","short"): sell += n
        tden=buy+sell
        trade_delta=(buy-sell)/tden if tden else 0.0

        spread=None
        if bid and ask and bid>0 and ask>=bid:
            spread=(ask-bid)/((ask+bid)/2)*100
        veto = spread is not None and spread > self.max_spread_pct
        L=S=0.0
        if book_imb > .05: L += min(45, 18+abs(book_imb)*35)
        elif book_imb < -.05: S += min(45, 18+abs(book_imb)*35)
        if trade_delta > .05: L += min(45, 18+abs(trade_delta)*35)
        elif trade_delta < -.05: S += min(45, 18+abs(trade_delta)*35)
        if spread is not None:
            quality=max(0.0,1-spread/self.max_spread_pct)
            if L>S: L += 10*quality
            elif S>L: S += 10*quality
        self.last={"book_imbalance":book_imb,"trade_delta":trade_delta,"spread_pct":spread,
                   "buy_notional":buy,"sell_notional":sell}
        return FamilyScore.build("order_flow",L,S,veto=veto,
            reason=f"book={book_imb:+.3f}, trades={trade_delta:+.3f}, spread={spread}")
