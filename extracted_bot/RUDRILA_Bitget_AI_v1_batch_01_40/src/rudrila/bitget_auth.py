from __future__ import annotations
import base64, hashlib, hmac, time
from dataclasses import dataclass
from urllib.parse import urlencode
from .settings import BitgetSettings
@dataclass
class SignedRequest:
    method:str; path:str; query:dict|None=None; body:str=''
    def headers(self,s:BitgetSettings):
        if not (s.api_key and s.api_secret and s.passphrase): raise RuntimeError('Demo API credentials are not configured.')
        ts=str(int(time.time()*1000)); q='?' + urlencode(self.query) if self.query else ''
        payload=ts+self.method.upper()+self.path+q+self.body
        sig=base64.b64encode(hmac.new(s.api_secret.encode(),payload.encode(),hashlib.sha256).digest()).decode()
        return {'ACCESS-KEY':s.api_key,'ACCESS-SIGN':sig,'ACCESS-TIMESTAMP':ts,'ACCESS-PASSPHRASE':s.passphrase,'Content-Type':'application/json','paptrading':'1'}
