from __future__ import annotations
import json,os
from dataclasses import dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONFIG_PATH=ROOT/'config'/'default.json'
@dataclass(frozen=True)
class BitgetSettings:
    mode:str; api_key:str; api_secret:str; passphrase:str; live_trading:bool
    rest_base:str='https://api.bitget.com'
    public_ws_demo:str='wss://wspap.bitget.com/v3/ws/public'
    private_ws_demo:str='wss://wspap.bitget.com/v3/ws/private'
    @classmethod
    def from_env(cls):
        mode=os.getenv('RUDRILA_MODE','demo').strip().lower()
        live=os.getenv('LIVE_TRADING','false').strip().lower()=='true'
        if mode!='demo': raise RuntimeError('This release is DEMO ONLY. Set RUDRILA_MODE=demo.')
        if live: raise RuntimeError('LIVE_TRADING must remain false in this release.')
        return cls(mode,os.getenv('BITGET_DEMO_API_KEY',''),os.getenv('BITGET_DEMO_API_SECRET',''),os.getenv('BITGET_DEMO_API_PASSPHRASE',''),False)
    def require_demo_credentials(self):
        if not (self.api_key and self.api_secret and self.passphrase):
            raise RuntimeError('Bitget Demo API credentials are not configured in environment variables.')
        return self

def load_config(): return json.loads(CONFIG_PATH.read_text())
