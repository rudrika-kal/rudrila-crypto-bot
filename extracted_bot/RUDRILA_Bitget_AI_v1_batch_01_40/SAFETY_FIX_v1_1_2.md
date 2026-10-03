# RUDRILA v1.1.2 Demo Safety Fix

Fixes verified after live Render diagnosis on 2026-10-01:

1. UTA account equity parsing now supports REST object payloads and private WS account payloads.
2. Demo USDT `bonus` is included as usable demo equity when `totalEquity`/`usdValue` are zero.
3. Removed fabricated 1000 USDT fallback; zero demo equity remains safely blocked.
4. A zero-equity account now reports `no positive demo equity` instead of false daily-loss/drawdown triggers.
5. Repeated polling of the same extreme RSS headline no longer extends the breaking-news freeze forever.
6. Dashboard now shows explicit safety reasons.
7. Real-money trading remains hard OFF.

Local test suite: 98/98 PASS.
