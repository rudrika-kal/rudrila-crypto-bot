from __future__ import annotations
from dataclasses import dataclass

@dataclass
class BreakingNewsState:
    active: bool=False
    direction: str="NEUTRAL"
    until_ms: int=0
    headline: str=""
    impact: float=0.0

class BreakingNewsGuard:
    def __init__(self, freeze_ms=60_000, extreme_score=70):
        self.freeze_ms=freeze_ms
        self.extreme_score=extreme_score
        self.state=BreakingNewsState()
        self.last_trigger_key=''

    def ingest(self, signed_news_score:float, headline:str, now_ms:int)->BreakingNewsState:
        # Do not extend the freeze every refresh for the same RSS headline.
        # A genuinely new extreme headline may start a new freeze.
        headline=(headline or '').strip()
        direction="LONG" if signed_news_score>0 else "SHORT"
        key=f"{direction}|{headline.lower()}" if headline else ''
        if abs(signed_news_score)>=self.extreme_score and key and key!=self.last_trigger_key:
            self.last_trigger_key=key
            self.state=BreakingNewsState(
                True, direction, now_ms+self.freeze_ms, headline, abs(signed_news_score)
            )
        return self.state

    def evaluate(self, now_ms:int, price_return_pct:float, orderflow_direction:str)->dict:
        s=self.state
        if not s.active:
            return {"allow":True,"reason":"no breaking-news lock","confirmed_direction":"NEUTRAL"}
        if now_ms < s.until_ms:
            return {"allow":False,"reason":"breaking-news freeze","confirmed_direction":s.direction}
        # Require price and order flow to confirm headline direction after the freeze.
        price_dir="LONG" if price_return_pct>0.05 else ("SHORT" if price_return_pct<-0.05 else "NEUTRAL")
        confirmed=(price_dir==s.direction and orderflow_direction==s.direction)
        self.state.active=False
        return {"allow":confirmed,
                "reason":"breaking-news confirmed" if confirmed else "breaking-news reaction not confirmed",
                "confirmed_direction":s.direction if confirmed else "NEUTRAL"}
