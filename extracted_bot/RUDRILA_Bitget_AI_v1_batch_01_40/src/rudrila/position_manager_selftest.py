from .position_manager import ManagedPosition, PositionManager

def _pos(**kw):
    d=dict(symbol='BTCUSDT',side='LONG',qty=.01,entry=100.0,stop=99.0,
           tp1=101.35,tp2=101.8,initial_r=1.0,opened_ms=1,
           entry_regime='BREAKOUT')
    d.update(kw)
    return ManagedPosition(**d)

def main():
    pm=PositionManager()

    # Noise: a single 1m flip must not close the trade.
    a=pm.update(_pos(),100.1,60_000,.4,mtf1='SHORT',momentum_direction='LONG')
    assert a.action!='CLOSE', a

    a=pm.update(_pos(),100.1,60_000,.4,mtf5='SHORT',mtf15='SHORT')
    assert a.action=='CLOSE' and a.reason=='MTF_5M_15M_REVERSAL', a

    a=pm.update(_pos(),100.1,60_000,.4,consensus_direction='SHORT',
                short_score=66,aligned_families=4,mtf5='SHORT')
    assert a.action=='CLOSE' and a.reason.startswith('STRONG_OPPOSITE'), a

    a=pm.update(_pos(),99.7,5*60_000,.4,mtf1='SHORT',
                momentum_direction='SHORT')
    assert a.action=='CLOSE' and a.reason=='FALSE_BREAKOUT', a

    a=pm.update(_pos(entry_regime='TREND',peak_r=1.3),100.6,10*60_000,.4)
    assert a.action=='CLOSE' and a.reason.startswith('TRAIL_GIVEBACK'), a

    a=pm.update(_pos(entry_regime='TREND'),100.1,46*60_000,.4)
    assert a.action=='CLOSE' and a.reason=='TIME_EXIT_45M', a

    print('POSITION_MANAGER_SELFTEST PASS',flush=True)

if __name__=='__main__':
    main()
