# RUDRILA Bitget AI v1.1.6 — Demo Account Readiness Fix

- Uses supported Bitget Demo API paths only: UTA v3 and Classic v2 with `paptrading: 1`.
- Deprecated synthetic SUMCBL fallback is disabled in runtime.
- Demo equity REST polling is throttled to once per 5 seconds instead of every 250 ms.
- Private WebSocket remains the preferred account source.
- Health/dashboard now report `account_status`, `funding_required`, trade permission, account mode, and sanitized UTA/Classic asset snapshots.
- A positive exchange-reported Demo balance is mandatory; no balance is fabricated from the mobile app UI.
- Real money remains hard disabled.
