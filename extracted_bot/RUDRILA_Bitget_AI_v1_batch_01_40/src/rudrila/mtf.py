from __future__ import annotations
from .trend import TrendFamily
from .signals import FamilyScore

class MultiTimeframeTrend:
    """1m execution context + 5m direction + 15m trend filter."""
    def __init__(self):
        self.t1=TrendFamily(); self.t5=TrendFamily(); self.t15=TrendFamily()
        self.last={}
    def update_1m(self,o,h,l,c,v): return self.t1.update(o,h,l,c,v)
    def update_5m(self,o,h,l,c,v): return self.t5.update(o,h,l,c,v)
    def update_15m(self,o,h,l,c,v): return self.t15.update(o,h,l,c,v)
    def score(self)->FamilyScore:
        s1=self.t1.update if False else None
        vals=[]
        for tf,obj,w in [('1m',self.t1,.20),('5m',self.t5,.45),('15m',self.t15,.35)]:
            d=obj.last
            if not d:
                vals.append((tf,FamilyScore.build(tf,0,0),w)); continue
            L=S=0.0
            e9,e20,e50,e200=d['ema9'],d['ema20'],d['ema50'],d['ema200']
            if e9>e20: L+=20
            elif e9<e20: S+=20
            if e20>e50: L+=25
            elif e20<e50: S+=25
            if e50>e200: L+=25
            elif e50<e200: S+=25
            if d['supertrend']>0: L+=15
            elif d['supertrend']<0: S+=15
            if d['plus_di']>d['minus_di']: L+=15
            elif d['minus_di']>d['plus_di']: S+=15
            vals.append((tf,FamilyScore.build(tf,L,S),w))
        L=sum(s.long*w for _,s,w in vals); S=sum(s.short*w for _,s,w in vals)
        # 15m strong opposition prevents high confidence but does not force a trade direction.
        s15=vals[2][1]
        if s15.direction=='LONG' and S>L: S*=.65
        if s15.direction=='SHORT' and L>S: L*=.65
        self.last={'1m':vals[0][1].direction,'5m':vals[1][1].direction,'15m':vals[2][1].direction,
                   'adx5':self.t5.last.get('adx',0) if self.t5.last else 0,
                   'adx15':self.t15.last.get('adx',0) if self.t15.last else 0}
        return FamilyScore.build('trend',L,S,reason=f"MTF 1m={self.last['1m']} 5m={self.last['5m']} 15m={self.last['15m']}")
