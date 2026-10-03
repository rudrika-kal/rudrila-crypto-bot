from __future__ import annotations
from collections import defaultdict,deque
from dataclasses import dataclass,field
import time

@dataclass
class SymbolState:
    symbol:str
    last_price:float|None=None
    bid:float|None=None
    ask:float|None=None
    mark_price:float|None=None
    index_price:float|None=None
    funding_rate:float|None=None
    open_interest:float|None=None
    next_funding_time:int|None=None
    volume24h:float|None=None
    last_update_ms:int=0
    trades:deque=field(default_factory=lambda:deque(maxlen=2000))
    candles:dict=field(default_factory=lambda:defaultdict(lambda:deque(maxlen=1000)))
    books5:dict|None=None

    def touch(self,ts_ms=None):
        self.last_update_ms=int(ts_ms or time.time()*1000)

    def is_stale(self,max_age_ms=3000):
        return (not self.last_update_ms) or int(time.time()*1000)-self.last_update_ms>max_age_ms

    @property
    def spread_pct(self):
        if not self.bid or not self.ask: return None
        mid=(self.bid+self.ask)/2
        return ((self.ask-self.bid)/mid)*100 if mid else None
