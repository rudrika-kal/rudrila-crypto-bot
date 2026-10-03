from __future__ import annotations
import asyncio, json, time
import websockets
from .bitget_execution import DemoOrderExecutor

class BitgetPrivateDemoWS:
    def __init__(self, executor:DemoOrderExecutor):
        self.executor=executor
        self.settings=executor.s
        self.connected=False
        self.logged_in=False
        self.last_message_ms=0
        self._stop=asyncio.Event()

    async def _heartbeat(self,ws):
        while not self._stop.is_set():
            await asyncio.sleep(30)
            await ws.send('ping')

    async def run(self,on_message=None):
        self._stop=asyncio.Event()
        async with websockets.connect(self.settings.private_ws_demo,ping_interval=None,close_timeout=5) as ws:
            self.connected=True
            await ws.send(json.dumps(self.executor.ws_login_payload(self.settings)))
            login_deadline=time.monotonic()+12
            while time.monotonic()<login_deadline:
                raw=await asyncio.wait_for(ws.recv(),timeout=12)
                if raw=='pong': continue
                msg=json.loads(raw); self.last_message_ms=int(time.time()*1000)
                if msg.get('event')=='login':
                    if str(msg.get('code')) not in ('0','00000'):
                        raise RuntimeError(f'Bitget private WS login failed: {msg}')
                    self.logged_in=True
                    break
                if msg.get('event')=='error':
                    raise RuntimeError(f'Bitget private WS error: {msg}')
            if not self.logged_in: raise RuntimeError('Bitget private WS login timeout')
            await ws.send(json.dumps(self.executor.private_subscriptions()))
            hb=asyncio.create_task(self._heartbeat(ws))
            try:
                while not self._stop.is_set():
                    raw=await asyncio.wait_for(ws.recv(),timeout=40)
                    if raw=='pong': continue
                    msg=json.loads(raw); self.last_message_ms=int(time.time()*1000)
                    if msg.get('event')=='error':
                        raise RuntimeError(f'Bitget private WS error: {msg}')
                    self.executor.handle_private(msg)
                    if on_message:
                        r=on_message(msg)
                        if asyncio.iscoroutine(r): await r
            finally:
                self._stop.set(); hb.cancel(); self.connected=False

    def stop(self): self._stop.set()
