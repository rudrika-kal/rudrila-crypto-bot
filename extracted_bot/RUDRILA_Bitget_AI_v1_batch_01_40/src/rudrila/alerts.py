from __future__ import annotations
import json,urllib.request,time

class AlertManager:
    def __init__(self,webhook_url:str|None=None,min_interval_sec=30):
        self.webhook_url=webhook_url; self.min_interval_sec=min_interval_sec; self.last={}
    def should_send(self,key):
        now=time.time(); old=self.last.get(key,0)
        if now-old<self.min_interval_sec: return False
        self.last[key]=now; return True
    def send(self,key:str,message:str,*,severity='INFO'):
        if not self.should_send(key): return {'sent':False,'reason':'rate_limited'}
        payload={'key':key,'severity':severity,'message':message,'ts':int(time.time())}
        if not self.webhook_url:
            return {'sent':False,'reason':'no_destination','payload':payload}
        req=urllib.request.Request(self.webhook_url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=8) as r: return {'sent':True,'status':r.status}
