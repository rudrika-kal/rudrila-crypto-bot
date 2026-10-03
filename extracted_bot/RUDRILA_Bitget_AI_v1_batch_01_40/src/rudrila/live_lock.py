from __future__ import annotations
import os

REQUIRED_PHRASE='I_ACCEPT_LIVE_TRADING_RISK'

def live_allowed(*,acceptance_passed:bool)->bool:
    return bool(acceptance_passed and os.getenv('LIVE_TRADING','false').lower()=='true' and
                os.getenv('LIVE_CONFIRMATION','')==REQUIRED_PHRASE)

def assert_live_locked():
    if os.getenv('LIVE_TRADING','false').lower()=='true':
        raise RuntimeError('Live trading remains locked until acceptance gate + explicit confirmation.')
