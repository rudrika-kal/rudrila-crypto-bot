from rudrila.position_manager import ManagedPosition, PositionManager

def pos(**kw):
    d=dict(symbol='BTCUSDT',side='LONG',qty=.01,entry=100.0,stop=99.0,
           tp1=101.35,tp2=101.8,initial_r=1.0,opened_ms=1,
           entry_regime='BREAKOUT')
    d.update(kw)
    return ManagedPosition(**d)

def test_single_1m_flip_does_not_exit():
    pm=PositionManager()
    a=pm.update(pos(),100.1,60_000,.4,mtf1='SHORT',momentum_direction='LONG')
    assert a.action!='CLOSE'

def test_mtf_reversal_exits():
    pm=PositionManager()
    a=pm.update(pos(),100.1,60_000,.4,mtf5='SHORT',mtf15='SHORT')
    assert a.action=='CLOSE' and a.reason=='MTF_5M_15M_REVERSAL'

def test_strong_opposite_consensus_exits():
    pm=PositionManager()
    a=pm.update(pos(),100.1,60_000,.4,consensus_direction='SHORT',
                short_score=66,aligned_families=4,mtf5='SHORT')
    assert a.action=='CLOSE' and a.reason.startswith('STRONG_OPPOSITE')

def test_false_breakout_exits():
    pm=PositionManager()
    a=pm.update(pos(),99.7,5*60_000,.4,mtf1='SHORT',
                momentum_direction='SHORT')
    assert a.action=='CLOSE' and a.reason=='FALSE_BREAKOUT'

def test_profit_giveback_exits():
    pm=PositionManager()
    p=pos(entry_regime='TREND',peak_r=1.3)
    a=pm.update(p,100.6,10*60_000,.4)
    assert a.action=='CLOSE' and a.reason.startswith('TRAIL_GIVEBACK')

def test_max_hold_exits():
    pm=PositionManager()
    a=pm.update(pos(entry_regime='TREND'),100.1,46*60_000,.4)
    assert a.action=='CLOSE' and a.reason=='TIME_EXIT_45M'
