from __future__ import annotations
import sqlite3,time
from .performance import metrics
from .acceptance import DemoAcceptanceGate

def report(path='runtime/rudrila_journal.sqlite3',days_running=0,private_ws_ok=True,order_reconcile_ok=True,stress_ok=True):
    db=sqlite3.connect(path)
    rows=db.execute('SELECT net_pnl FROM trades ORDER BY closed_ms').fetchall()
    pnls=[float(x[0] or 0) for x in rows]
    eq=1000.0; curve=[]
    for p in pnls: eq+=p; curve.append(eq)
    m=metrics(pnls,curve)
    gate=DemoAcceptanceGate().evaluate(m,private_ws_ok=private_ws_ok,order_reconcile_ok=order_reconcile_ok,stress_ok=stress_ok,days=days_running)
    return {'metrics':m,'acceptance':gate}
