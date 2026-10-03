# RUDRILA Bitget AI v1.1 — Demo Trading Ready

This release is intentionally **Bitget Demo only**. Real-money trading is hard-disabled.

## What is fully wired
- Bitget UTA v3 public WebSocket market data for BTCUSDT and ETHUSDT.
- Private Demo WebSocket login + order/fill/position/account reconciliation.
- Signed Demo REST orders with `paptrading: 1`.
- Instrument precision/minimum-size validation before order placement.
- Trend, momentum, Fibonacci/structure, order flow, volume/derivatives, volatility/execution, and live news/macro families.
- Fed + SEC official RSS plus CoinDesk/Cointelegraph lower-weight crypto feeds.
- Risk sizing, daily loss/drawdown gates, stale-data/spread/order-state safety vetoes.
- SQLite journal and health file.

## Required once you create the Bitget Demo API key
Keep credentials in environment variables, not source files.

1. `python -m rudrila.main --public-preflight`
2. `python -m rudrila.main --private-preflight`
3. `python -m rudrila.main --private-ws-smoke 20`
4. `python -m rudrila.main --demo-run 3600`

For long-running Demo validation use the Docker Compose file in `deploy/` after setting the three Demo environment variables.

## Important validation gate
A bot can be operational before it is statistically validated. This package is operationally ready for Demo trading, but no fixed win rate is claimed. The acceptance gate still requires a meaningful forward sample after fees/slippage/funding before live-money consideration.


## v1.1.4 mobile Demo fallback
If Bitget UTA v3 Demo reports zero account equity while the Bitget mobile Futures Demo screen shows SUSDT, runtime now safely checks the Classic Futures Demo account using the same Demo API key and `paptrading: 1`. When positive SUSDT/USDT equity is found, execution switches to `CLASSIC_V2_DEMO`, positions are polled from Classic Futures, and orders are routed to the Classic Demo order endpoint. Market analysis remains on BTCUSDT/ETHUSDT real-market feeds. Real money remains hard-disabled.
