# v1.1.1 Demo Monitoring

Added live per-symbol decision visibility for BTCUSDT and ETHUSDT.

The dashboard and `/health.json` now expose the last completed 1m decision: consensus, long/short score, required threshold, aligned family count, regime, all seven family scores, safety state, breaking-news state, and the exact block/rejection reason.

Runtime stdout now emits `SIGNAL`, `BLOCK`, `ORDER_REJECTED`, and `ORDER_SUBMITTED` lines.

This does not loosen entry criteria and does not enable real-money trading.
