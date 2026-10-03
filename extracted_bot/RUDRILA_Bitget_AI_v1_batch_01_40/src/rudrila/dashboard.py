from __future__ import annotations
import html,json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

def _esc(x):
    return html.escape(str(x if x is not None else '—'))

def render_dashboard(data:dict)->str:
    signals=data.get('signals') or {}
    cards=[]
    for sym in data.get('symbols') or sorted(signals):
        d=signals.get(sym) or {}
        fam=d.get('families') or {}
        fam_rows=''.join(
            '<tr><td>'+_esc(name)+'</td><td>'+_esc(v.get('direction'))+'</td><td>'+_esc(v.get('long'))+'</td><td>'+_esc(v.get('short'))+'</td><td>'+_esc(v.get('confidence'))+'</td><td>'+('YES' if v.get('veto') else 'no')+'</td></tr>'
            for name,v in fam.items()
        ) or '<tr><td colspan="6">Waiting for first closed 1m decision…</td></tr>'
        cards.append(
            '<section class="card"><h2>'+_esc(sym)+'</h2>'
            '<div class="grid">'
            '<div><span>Status</span><b>'+_esc(d.get('status','WAITING'))+'</b></div>'
            '<div><span>Consensus</span><b>'+_esc(d.get('consensus'))+'</b></div>'
            '<div><span>Score</span><b>'+_esc(d.get('actual_score'))+' / '+_esc(d.get('required_score'))+'</b></div>'
            '<div><span>Aligned</span><b>'+_esc(d.get('aligned_families'))+' / '+_esc(d.get('minimum_aligned_families'))+'</b></div>'
            '<div><span>Regime</span><b>'+_esc(d.get('regime'))+'</b></div>'
            '<div><span>Price</span><b>'+_esc(d.get('price'))+'</b></div>'
            '</div>'
            '<p class="reason"><strong>Why:</strong> '+_esc(d.get('reason','Waiting for first closed 1m decision'))+'</p>'
            '<p class="mini">Safety: '+_esc(d.get('safety_allow'))+' · Safety reasons: '+_esc(', '.join(d.get('safety_reasons') or []))+' · Breaking news: '+_esc(d.get('breaking_reason'))+' · Spread: '+_esc(d.get('spread_pct'))+'</p>'
            '<table><thead><tr><th>Family</th><th>Dir</th><th>Long</th><th>Short</th><th>Conf</th><th>Veto</th></tr></thead><tbody>'+fam_rows+'</tbody></table>'
            '</section>'
        )
    positions=data.get('open_positions') or []
    pos_txt=', '.join(f"{p.get('symbol')} {p.get('side')} {p.get('size')}" for p in positions) or 'None'
    return (
        '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="5"><title>RUDRILA Bitget AI</title>'
        '<style>body{font-family:system-ui,sans-serif;margin:0;background:#111;color:#eee}main{max-width:980px;margin:auto;padding:16px}.top,.card{background:#1b1b1b;border:1px solid #333;border-radius:14px;padding:14px;margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.grid div{background:#242424;border-radius:10px;padding:10px}span{display:block;color:#aaa;font-size:12px}b{font-size:16px}.reason{padding:10px;background:#242424;border-radius:10px}.mini{color:#bbb;font-size:13px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border-bottom:1px solid #333;padding:7px;text-align:left}@media(max-width:650px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}table{font-size:10px}th,td{padding:5px}}</style>'
        '</head><body><main><div class="top"><h1>RUDRILA Bitget AI — DEMO</h1>'
        '<p>Status: <b>'+_esc(data.get('status'))+'</b> · Account: <b>'+_esc(data.get('account_status','UNKNOWN'))+'</b> · Backend: <b>'+_esc(data.get('execution_backend','UTA_V3_DEMO'))+'</b> · Margin: <b>'+_esc(data.get('demo_margin_coin','USDT'))+'</b> · Private WS: <b>'+_esc(data.get('private_ws'))+'</b> · Equity: <b>'+_esc(data.get('equity'))+'</b></p>'
        '<p>Open positions: '+_esc(pos_txt)+' · Orders seen: '+_esc(data.get('orders_seen',0))+' · Fills seen: '+_esc(data.get('fills_seen',0))+'</p>'
        + ('<p class="reason"><strong>Funding required:</strong> Bitget Demo API balance is zero. In Bitget web Demo mode use Assets → Deposit/claim demo coins. The bot will automatically detect the balance on its next refresh.</p>' if data.get('funding_required') else '')
        + '<p class="mini">Trade permission: '+_esc(data.get('trade_permission_ok'))+' · Account mode: '+_esc(data.get('account_mode'))+' · Hold mode: '+_esc(data.get('hold_mode'))+' · Auto refresh: 5 sec · Real money remains OFF.</p></div>'+''.join(cards)+'</main></body></html>'
    )

class DashboardHandler(BaseHTTPRequestHandler):
    health_path=Path('runtime/health.json')
    def do_GET(self):
        try:
            data=json.loads(self.health_path.read_text()) if self.health_path.exists() else {'status':'unknown'}
        except Exception:
            data={'status':'fatal','reason':'invalid health file'}
        if self.path=='/health.json':
            b=json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers(); self.wfile.write(b); return
        b=render_dashboard(data).encode()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.end_headers(); self.wfile.write(b)
    def log_message(self,*a):
        pass

def serve(host='0.0.0.0',port=8080):
    ThreadingHTTPServer((host,port),DashboardHandler).serve_forever()
