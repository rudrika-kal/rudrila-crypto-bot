from __future__ import annotations
import ast,re
from pathlib import Path

SECRET_PATTERNS=[r'(?i)api[_-]?secret\s*=\s*["\'][^"\']+["\']',r'(?i)passphrase\s*=\s*["\'][^"\']+["\']']

def audit_tree(root:str|Path)->dict:
    root=Path(root); py=list(root.rglob('*.py')); syntax=[]; secrets=[]
    for p in py:
        txt=p.read_text(errors='ignore')
        try: ast.parse(txt)
        except SyntaxError as e: syntax.append({'file':str(p),'error':str(e)})
        for pat in SECRET_PATTERNS:
            if re.search(pat,txt): secrets.append(str(p))
    return {'python_files':len(py),'syntax_errors':syntax,'possible_embedded_secrets':sorted(set(secrets)),
            'pass':not syntax and not secrets}
