# RUDRILA Bitget AI v1.0 — Frozen Specification (Steps 1–5)

## Safety mode
- Demo only. Live trading is hard-disabled in this batch.
- Symbols: BTCUSDT, ETHUSDT
- Product: Bitget UTA USDT Futures
- Timeframes: 1m / 5m / 15m
- No forced trades.

## Decision framework
Seven independent signal families:
- Order Flow: 20
- Market Structure + Fibonacci: 18
- Trend: 15
- News + Macro: 15
- Momentum: 12
- Volume + Derivatives: 12
- Volatility + Execution Quality: 8

Initial entry gate:
- Composite score >= 82/100
- Minimum 5 of 7 families aligned
- Hard safety vetoes must all pass
- Adaptive score range: 78–88 (later validated by backtest; not active yet)

## Risk defaults
- Risk/trade: 0.25% of account
- Daily loss cap: 1.5%
- Total drawdown cap: 5%
- Max open positions: 2
- Correlated same-direction BTC/ETH exposure: max 1 by default

## Data architecture
- WebSocket-first
- Public demo WS: wss://wspap.bitget.com/v3/ws/public
- Private demo WS: wss://wspap.bitget.com/v3/ws/private
- REST base: https://api.bitget.com
- Demo REST requests must include `paptrading: 1`
- Heartbeat: ping every 30s; reconnect on missing pong / disconnect
- Stale-data veto: 3000ms initial threshold

## Steps 1–5 acceptance
1. Specification frozen: CLEAR
2. Demo integration scaffold: READY; private authentication cannot be marked CLEAR until the user's demo API credentials are configured locally and tested.
3. Modular project structure: CLEAR
4. Public market-data engine code: CLEAR; live runtime connection test is performed on the target runtime.
5. Incremental calculation engine: CLEAR; deterministic tests included.
