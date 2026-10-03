from __future__ import annotations
from dataclasses import dataclass
from .consensus import ConsensusResult

@dataclass(frozen=True)
class EntryDecision:
    enter: bool
    side: str
    required_score: float
    actual_score: float
    aligned_families: int
    reason: str

class EntryRules:
    def __init__(self, base=82, min_aligned=5, *, fast_enabled=True,
                 fast_impulse_score=45, trend_continuation_score=60,
                 fast_min_aligned=4, max_fast_spread_pct=0.03,
                 min_fast_depth_notional=10000):
        self.base=base
        self.min_aligned=min_aligned
        self.fast_enabled=bool(fast_enabled)
        self.fast_impulse_score=float(fast_impulse_score)
        self.trend_continuation_score=float(trend_continuation_score)
        self.fast_min_aligned=int(fast_min_aligned)
        self.max_fast_spread_pct=float(max_fast_spread_pct)
        self.min_fast_depth_notional=float(min_fast_depth_notional)
    def threshold(self, regime:str)->float:
        return {
          "TREND":80.0,
          "BREAKOUT":84.0,
          "RANGE":86.0,
          "PANIC":999.0,
          "LOW_LIQUIDITY":999.0
        }.get(regime, self.base)
    def decide(self, c:ConsensusResult, regime:str, breaking_allow:bool=True,
               risk_allow:bool=True, cooldown:bool=False)->EntryDecision:
        req=self.threshold(regime)
        score=c.long_score if c.direction=="LONG" else c.short_score if c.direction=="SHORT" else 0
        reasons=[]
        if c.direction=="NEUTRAL": reasons.append("neutral consensus")
        if c.veto: reasons.append("hard veto")
        if c.aligned_families<self.min_aligned: reasons.append("not enough independent families")
        if score<req: reasons.append("score below threshold")
        if not breaking_allow: reasons.append("breaking-news guard")
        if not risk_allow: reasons.append("risk gate")
        if cooldown: reasons.append("cooldown")
        ok=not reasons
        return EntryDecision(ok,c.direction if ok else "NONE",req,score,c.aligned_families,
                             "entry approved" if ok else "; ".join(reasons))

    def decide_directional_core(self, c:ConsensusResult, scores:dict, regime:str, *,
                                candle_ret_pct:float, candle_range_pct:float,
                                atr_pct:float, spread_pct:float|None,
                                depth_notional:float|None,
                                mtf5:str='NEUTRAL', mtf15:str='NEUTRAL',
                                breakout_up:bool=False, breakout_down:bool=False,
                                breaking_allow:bool=True, risk_allow:bool=True,
                                cooldown:bool=False)->EntryDecision:
        # Secondary path for real fast moves and strong trend continuation.
        # It ignores neutral news/volatility direction, but it never bypasses
        # hard veto, execution safety, breaking-news, cooldown or risk gates.
        side=c.direction
        if not self.fast_enabled:
            return EntryDecision(False,'NONE',self.fast_impulse_score,0.0,0,'directional core disabled')
        if side not in ('LONG','SHORT'):
            return EntryDecision(False,'NONE',self.fast_impulse_score,0.0,0,'directional core: neutral consensus')

        weights={'order_flow':20,'structure_fibonacci':18,'trend':15,'momentum':12,'volume_derivatives':12}
        total=sum(weights.values())
        aligned=0
        raw=0.0
        for name,w in weights.items():
            x=scores[name]
            val=x.long if side=='LONG' else x.short
            raw += w*(val/100.0)
            if x.direction==side:
                aligned += 1
        core_score=raw/total*100.0

        spread_ok=spread_pct is not None and spread_pct<=self.max_fast_spread_pct
        depth_ok=depth_notional is not None and depth_notional>=self.min_fast_depth_notional
        price_dir=(candle_ret_pct>0 if side=='LONG' else candle_ret_pct<0)
        breakout_ok=breakout_up if side=='LONG' else breakout_down
        move_trigger=(abs(candle_ret_pct)>=max(0.28,atr_pct*0.70)
                      or candle_range_pct>=max(0.45,atr_pct*1.60))
        micro=sum(scores[n].direction==side for n in ('order_flow','structure_fibonacci','momentum'))
        fast_ok=(move_trigger and price_dir and aligned>=self.fast_min_aligned and core_score>=self.fast_impulse_score
                 and micro>=2 and (mtf5==side or breakout_ok))
        continuation_ok=(regime in ('TREND','BREAKOUT','NORMAL') and aligned>=self.fast_min_aligned
                         and core_score>=self.trend_continuation_score and mtf5==side and mtf15==side
                         and scores['structure_fibonacci'].direction==side
                         and scores['momentum'].direction==side
                         and (scores['order_flow'].direction==side
                              or scores['volume_derivatives'].direction==side))

        reasons=[]
        if regime in ('LOW_LIQUIDITY','RANGE'):
            reasons.append(f'directional core disabled in {regime}')
        if c.veto:
            reasons.append('hard veto')
        if not spread_ok:
            reasons.append('fast-path spread too wide/unavailable')
        if not depth_ok:
            reasons.append('fast-path depth too low/unavailable')
        if not breaking_allow:
            reasons.append('breaking-news guard')
        if not risk_allow:
            reasons.append('risk gate')
        if cooldown:
            reasons.append('cooldown')
        trigger='FAST_IMPULSE' if fast_ok else 'TREND_CONTINUATION' if continuation_ok else ''
        if not trigger:
            reasons.append(f'core setup incomplete score={core_score:.1f} aligned={aligned}/5')
        ok=bool(trigger) and not reasons
        req=self.fast_impulse_score if trigger=='FAST_IMPULSE' else self.trend_continuation_score
        return EntryDecision(ok,side if ok else 'NONE',req,round(core_score,3),aligned,
                             f'{trigger.lower()} entry approved' if ok else '; '.join(reasons))
