from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math, re, hashlib
from .signals import FamilyScore

@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_ms: int
    body: str = ""
    url: str = ""

class NewsMacroEngine:
    POSITIVE = {
      "approval":2.2,"approved":2.2,"adoption":1.8,"partnership":1.2,"launch":1.0,
      "inflows":1.8,"inflow":1.4,"upgrade":1.1,"record high":1.5,"rate cut":1.5,
      "easing":1.1,"legal":1.0,"license":1.1,"integration":1.0,"buyback":1.0,
      "reserve":.8,"institutional":.8
    }
    NEGATIVE = {
      "hack":2.8,"hacked":2.8,"exploit":2.8,"breach":2.2,"insolvency":3.0,
      "bankruptcy":3.0,"ban":2.4,"lawsuit":1.3,"investigation":1.2,"outflows":1.7,
      "depeg":3.0,"liquidation":1.4,"shutdown":2.0,"sanction":1.4,"rate hike":1.5,
      "hawkish":1.1,"fraud":2.0,"stolen":2.5
    }
    HIGH_IMPACT = {
      "etf":1.5,"federal reserve":1.4,"fed ":1.2,"cpi":1.3,"inflation":1.2,
      "sec ":1.3,"regulation":1.2,"stablecoin":1.2,"exchange":1.1,"bitcoin":1.0,
      "ethereum":1.0,"btc":1.0,"eth":1.0,"treasury":1.0,"geopolitical":1.0
    }
    SOURCE_WEIGHT = {
      "official":1.35,"regulator":1.30,"central_bank":1.30,"exchange_official":1.20,
      "tier1_media":1.05,"crypto_media":.90,"social":.45,"unknown":.60
    }

    def __init__(self, half_life_minutes=45):
        self.half_life_minutes=half_life_minutes
        self.seen={}
        self.last={}

    @staticmethod
    def normalize(text:str)->str:
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def token_similarity(a:str,b:str)->float:
        A=set(NewsMacroEngine.normalize(a).split())
        B=set(NewsMacroEngine.normalize(b).split())
        return len(A&B)/len(A|B) if A and B else 0.0

    def dedupe(self, items:list[NewsItem])->list[NewsItem]:
        out=[]
        for x in sorted(items,key=lambda z:z.published_ms,reverse=True):
            if any(self.token_similarity(x.title,y.title)>=0.72 for y in out):
                continue
            out.append(x)
        return out

    def score_item(self, item:NewsItem, now_ms:int, source_class="unknown")->dict:
        text=(item.title+" "+item.body).lower()
        pos=sum(w for k,w in self.POSITIVE.items() if k in text)
        neg=sum(w for k,w in self.NEGATIVE.items() if k in text)
        impact=1.0+sum(w for k,w in self.HIGH_IMPACT.items() if k in text)
        source_w=self.SOURCE_WEIGHT.get(source_class,self.SOURCE_WEIGHT["unknown"])
        age_min=max(0.0,(now_ms-item.published_ms)/60000)
        decay=0.5**(age_min/max(self.half_life_minutes,1e-9))
        raw=(pos-neg)*18*impact*source_w*decay
        score=max(-100.0,min(100.0,raw))
        relevance=min(100.0,20*impact)
        return {"score":score,"impact":impact,"relevance":relevance,"age_min":age_min,
                "source_weight":source_w,"title":item.title,"source":item.source}

    def aggregate(self, items:list[NewsItem], source_classes:dict[str,str]|None=None,
                  now_ms:int|None=None)->FamilyScore:
        now_ms=now_ms or int(datetime.now(timezone.utc).timestamp()*1000)
        source_classes=source_classes or {}
        unique=self.dedupe(items)
        details=[self.score_item(x,now_ms,source_classes.get(x.source,"unknown")) for x in unique]
        # Highest-impact recent stories dominate; many duplicates do not.
        details=sorted(details,key=lambda d:abs(d["score"]),reverse=True)[:8]
        signed=sum(d["score"]*(1.0/(1+i*.35)) for i,d in enumerate(details))
        signed=max(-100.0,min(100.0,signed))
        L=max(0.0,signed)
        S=max(0.0,-signed)
        # Neutral news gets low directional score.
        self.last={"signed_score":signed,"stories":details,"unique_count":len(unique)}
        return FamilyScore.build("news_macro",L,S,
             reason=f"news={signed:+.1f}, unique={len(unique)}")
