from __future__ import annotations
import json, sqlite3, time
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS decisions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, ts_ms INTEGER NOT NULL, symbol TEXT NOT NULL,
 regime TEXT, side TEXT, composite REAL, aligned INTEGER, news REAL,
 family_json TEXT, reason TEXT, entered INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trades(
 id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id TEXT UNIQUE, symbol TEXT, side TEXT,
 opened_ms INTEGER, closed_ms INTEGER, entry REAL, exit REAL, qty REAL,
 gross_pnl REAL, fees REAL, funding REAL, slippage REAL, net_pnl REAL,
 exit_reason TEXT, decision_id INTEGER
);
'''

class TradeJournal:
    def __init__(self,path='runtime/rudrila_journal.sqlite3'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.executescript(SCHEMA); self.db.commit()
    def log_decision(self, *, ts_ms:int, symbol:str, regime:str, side:str, composite:float,
                     aligned:int, news:float, families:dict, reason:str, entered=False)->int:
        cur=self.db.execute('INSERT INTO decisions(ts_ms,symbol,regime,side,composite,aligned,news,family_json,reason,entered) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (ts_ms,symbol,regime,side,composite,aligned,news,json.dumps(families,sort_keys=True),reason,int(entered)))
        self.db.commit(); return int(cur.lastrowid)
    def log_trade(self, **t):
        cols=['trade_id','symbol','side','opened_ms','closed_ms','entry','exit','qty','gross_pnl','fees','funding','slippage','net_pnl','exit_reason','decision_id']
        vals=[t.get(k) for k in cols]
        self.db.execute('INSERT OR REPLACE INTO trades('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',vals)
        self.db.commit()
    def summary(self):
        row=self.db.execute('SELECT COUNT(*),COALESCE(SUM(net_pnl),0),COALESCE(AVG(net_pnl),0) FROM trades').fetchone()
        return {'trades':row[0],'net_pnl':row[1],'avg_net_pnl':row[2]}
    def close(self): self.db.close()
