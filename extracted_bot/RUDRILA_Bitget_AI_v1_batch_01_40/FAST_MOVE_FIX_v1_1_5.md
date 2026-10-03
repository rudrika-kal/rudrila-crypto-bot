# RUDRILA Bitget AI v1.1.5 Fast-Move Fix

- books5 top-of-book now overrides temporarily lagged ticker bid/ask for execution spread.
- LOW_LIQUIDITY classification now combines spread with actual depth instead of treating any transient wide ticker spread as thin liquidity.
- panic/fast movement no longer creates an automatic execution veto when spread and depth remain healthy.
- added a fail-closed directional-core path for fast impulse and strong trend continuation.
- fast path still requires 4/5 core directional families, healthy spread/depth, safety gate, breaking-news gate, cooldown, position limits, and the normal risk engine.
- no forced trades; live trading remains locked OFF.
- regression suite: 115 tests PASS.
