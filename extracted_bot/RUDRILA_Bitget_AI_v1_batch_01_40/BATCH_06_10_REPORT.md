# RUDRILA Bitget AI — Batch 6–10 Report

## Step 6 — Trend Family: CLEAR
Incremental EMA 9/20/50/200, rolling VWAP, Wilder-style ADX/DMI, Supertrend.
Returns LONG / SHORT / NEUTRAL family score in 0–100.

## Step 7 — Momentum Family: CLEAR
RSI, Stoch RSI, MACD histogram, ROC and candle impulse.
Exhaustion penalties are included; scores are bounded 0–100.

## Step 8 — Market Structure + Fibonacci: CLEAR
Rolling swing high/low, breakout checks, retest tolerance,
23.6/38.2/50/61.8/78.6 retracements, 127.2/161.8 extensions,
and 50–61.8 golden-pocket rejection logic.

## Step 9 — Order Flow: CLEAR
5-level weighted order-book imbalance, recent aggressive buy/sell trade delta,
spread-quality adjustment and hard spread veto.

## Step 10 — Volume + Derivatives: CLEAR
Relative volume, OBV, price-volume confirmation, open-interest change,
funding crowding context. Funding and OI are parsed directly from Bitget
USDT-futures ticker pushes.

## Important
- No live-money execution exists in this batch.
- Demo private authentication remains pending until the user creates a Bitget Demo API key.
- These signals are not claimed to produce a fixed win rate. They must pass later backtests,
  walk-forward tests and Bitget Demo forward testing before any live-money consideration.
