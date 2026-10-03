from __future__ import annotations
from .trend import TrendFamily
from .momentum import MomentumFamily
from .structure_fib import StructureFibFamily
from .order_flow import OrderFlowFamily
from .volume_derivatives import VolumeDerivativesFamily
from .indicators import WilderATR

class SignalEngine0610:
    def __init__(self):
        self.trend=TrendFamily()
        self.momentum=MomentumFamily()
        self.structure=StructureFibFamily()
        self.orderflow=OrderFlowFamily()
        self.volume=VolumeDerivativesFamily()
        self.atr=WilderATR(14)
        self.latest={}

    def update_candle(self,o,h,l,c,v, *, book=None, trades=(), bid=None, ask=None,
                      funding_rate=None, open_interest=None):
        atr=self.atr.update(h,l,c)
        scores={
            "trend":self.trend.update(o,h,l,c,v),
            "momentum":self.momentum.update(o,h,l,c,v),
            "structure_fibonacci":self.structure.update(o,h,l,c,v,atr),
            "order_flow":self.orderflow.score(book,trades,bid,ask),
            "volume_derivatives":self.volume.update(c,v,funding_rate,open_interest),
        }
        self.latest=scores
        return scores
