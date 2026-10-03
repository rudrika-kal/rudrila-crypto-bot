from __future__ import annotations
from collections import deque
from dataclasses import dataclass
@dataclass
class EMA:
    period:int; value:float|None=None
    def update(self,x):
        a=2/(self.period+1); self.value=x if self.value is None else a*x+(1-a)*self.value; return self.value
@dataclass
class WilderRSI:
    period:int=14; prev:float|None=None; avg_gain:float|None=None; avg_loss:float|None=None; value:float=50.0
    def update(self,close):
        if self.prev is None: self.prev=close; return self.value
        d=close-self.prev; self.prev=close; g=max(d,0); l=max(-d,0)
        if self.avg_gain is None: self.avg_gain,self.avg_loss=g,l
        else:
            a=1/self.period; self.avg_gain=a*g+(1-a)*self.avg_gain; self.avg_loss=a*l+(1-a)*self.avg_loss
        if self.avg_loss==0: self.value=100.0 if self.avg_gain and self.avg_gain>0 else 50.0
        else:
            rs=self.avg_gain/self.avg_loss; self.value=100-100/(1+rs)
        return self.value
@dataclass
class WilderATR:
    period:int=14; prev_close:float|None=None; value:float|None=None
    def update(self,h,l,c):
        tr=(h-l) if self.prev_close is None else max(h-l,abs(h-self.prev_close),abs(l-self.prev_close)); self.prev_close=c
        if self.value is None: self.value=tr
        else:
            a=1/self.period; self.value=a*tr+(1-a)*self.value
        return self.value
class RollingVWAP:
    def __init__(self,maxlen=500): self.items=deque(maxlen=maxlen); self.pv=0.; self.vol=0.
    def update(self,p,v):
        if len(self.items)==self.items.maxlen:
            op,ov=self.items[0]; self.pv-=op*ov; self.vol-=ov
        self.items.append((p,v)); self.pv+=p*v; self.vol+=v
        return self.pv/self.vol if self.vol>0 else p
class FastIndicatorPack:
    def __init__(self):
        self.ema9=EMA(9); self.ema20=EMA(20); self.ema50=EMA(50); self.ema200=EMA(200); self.rsi14=WilderRSI(14); self.atr14=WilderATR(14); self.vwap=RollingVWAP(500)
    def update_candle(self,o,h,l,c,v):
        return {'ema9':self.ema9.update(c),'ema20':self.ema20.update(c),'ema50':self.ema50.update(c),'ema200':self.ema200.update(c),'rsi14':self.rsi14.update(c),'atr14':self.atr14.update(h,l,c),'vwap':self.vwap.update(c,v)}
