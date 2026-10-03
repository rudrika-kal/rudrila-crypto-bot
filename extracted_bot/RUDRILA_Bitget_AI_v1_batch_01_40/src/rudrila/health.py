from __future__ import annotations
import json,time
from pathlib import Path
class HealthState:
    def __init__(self,path='runtime/health.json'): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def write(self,data:dict|None=None,**kwargs):
        x=dict(data or {}); x.update(kwargs); x.setdefault('ts_ms',int(time.time()*1000)); self.path.write_text(json.dumps(x,indent=2,sort_keys=True)); return x
    def read(self):
        if not self.path.exists(): return {'status':'unknown'}
        try: return json.loads(self.path.read_text())
        except Exception: return {'status':'fatal','reason':'invalid health file'}
