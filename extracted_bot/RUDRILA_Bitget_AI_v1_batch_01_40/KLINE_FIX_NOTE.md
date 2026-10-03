# v1.1.1 Demo Kline Fix

Fixes Bitget UTA v3 WebSocket candlestick parsing. The UTA `topic=kline` channel pushes candle objects (`start`, `open`, `high`, `low`, `close`, `volume`, `turnover`), while the runtime had expected REST-style arrays. The public WebSocket adapter now normalizes both formats into one canonical array and replaces repeated updates for the same open candle instead of appending duplicates.

Validation: 91/91 cumulative tests pass, including UTA object parsing and repeated-open-candle update tests.
