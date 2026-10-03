from __future__ import annotations
import hashlib,json,shutil,time
from pathlib import Path

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def backup_files(files:list[str],dest_root='runtime/backups')->dict:
    stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
    d=Path(dest_root)/stamp; d.mkdir(parents=True,exist_ok=True)
    manifest={}
    for f in files:
        p=Path(f)
        if p.exists():
            target=d/p.name; shutil.copy2(p,target); manifest[p.name]=sha256(target)
    (d/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return {'dir':str(d),'manifest':manifest}
