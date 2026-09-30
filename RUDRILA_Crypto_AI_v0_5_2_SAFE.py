#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import math
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.5.2-safe-paper-audit"

CONFIG = {
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "timeframes": ["1m", "5m", "15m"],
    "ohlcv_limit": 500,

    "starting_balance_usdt": 100.0,

    # Faster paper scalping, but risk stays controlled.
    "risk_per_trade_pct": 0.30,
    "max_daily_loss_pct": 1.20,
    "max_total_drawdown_pct": 4.0,
    "max_open_positions": 2,

    # Lower than v0.4 to allow more qualified setups.
    "min_confidence": 101,
    "entry_enabled": False,  # independent safety gate until backtest passes

    # Faster profit booking. Minimum stop is still wide enough
    # that simulated fees/slippage do not dominate every trade.
    "reward_risk_ratio": 1.40,
    "min_stop_pct": 0.35,
    "atr_stop_multiple": 0.80,

    "fee_rate_pct": 0.10,
    "slippage_pct": 0.03,
    "max_spread_pct": 0.05,

    # Faster scan cadence.
    "poll_seconds": 20,

    # Force shorter holding periods.
    "max_hold_minutes": 45,
    "cooldown_minutes": 8,

    # Once price moves far enough in our favor, protect part of the move.
    "profit_lock_trigger_r": 0.90,

    "paper_only": True,
}

if os.environ.get("GITHUB_ACTIONS") == "true":
    DATA_DIR = Path("state")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE = DATA_DIR / "rudrila_state_v05.json"
    LOG_FILE = DATA_DIR / "rudrila_v05_trades.jsonl"
else:
    STATE_FILE = Path.home() / ".rudrila_crypto_paper_state_v05.json"
    LOG_FILE = Path.home() / "rudrila_v05_trades.jsonl"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def get_json(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"RUDRILA-Crypto-AI/{VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_ohlcv(symbol, tf, limit=500):
    errs = []

    # GitHub-hosted runners can be geo-blocked by some exchanges.
    # Kraken is the primary cloud feed; Coinbase is a free fallback.
    pair = "XBTUSD" if symbol.startswith("BTC") else "ETHUSD"
    kraken_interval = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}.get(tf, 1)

    try:
        q = urllib.parse.urlencode({"pair": pair, "interval": kraken_interval})
        d = get_json("https://api.kraken.com/0/public/OHLC?" + q)
        if d.get("error"):
            raise RuntimeError(",".join(d["error"]))
        result = d.get("result", {})
        key = next(k for k in result.keys() if k != "last")
        raw = result[key]
        rows = [
            {
                "timestamp": int(float(x[0])) * 1000,
                "open": float(x[1]),
                "high": float(x[2]),
                "low": float(x[3]),
                "close": float(x[4]),
                "volume": float(x[6]),
            }
            for x in raw[-limit:]
        ]
        if len(rows) >= 220:
            return rows, "Kraken"
    except Exception as e:
        errs.append("Kraken:" + str(e))

    try:
        product = "BTC-USD" if symbol.startswith("BTC") else "ETH-USD"
        gran = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}.get(tf, 60)
        d = get_json(
            "https://api.exchange.coinbase.com/products/"
            + product
            + "/candles?"
            + urllib.parse.urlencode({"granularity": gran})
        )
        d = sorted(d, key=lambda x: x[0])
        rows = [
            {
                "timestamp": int(x[0]) * 1000,
                "open": float(x[3]),
                "high": float(x[2]),
                "low": float(x[1]),
                "close": float(x[4]),
                "volume": float(x[5]),
            }
            for x in d[-limit:]
        ]
        if len(rows) >= 220:
            return rows, "Coinbase"
    except Exception as e:
        errs.append("Coinbase:" + str(e))

    try:
        q = urllib.parse.urlencode(
            {"symbol": symbol, "interval": tf, "limit": min(limit, 1000)}
        )
        d = get_json("https://api.binance.com/api/v3/klines?" + q)
        rows = [
            {
                "timestamp": int(x[0]),
                "open": float(x[1]),
                "high": float(x[2]),
                "low": float(x[3]),
                "close": float(x[4]),
                "volume": float(x[5]),
            }
            for x in d
        ]
        if len(rows) >= 220:
            return rows, "Binance"
    except Exception as e:
        errs.append("Binance:" + str(e))

    raise RuntimeError("OHLCV unavailable | " + " | ".join(errs))

def fetch_orderbook(symbol):
    errs = []
    pair = "XBTUSD" if symbol.startswith("BTC") else "ETHUSD"

    try:
        q = urllib.parse.urlencode({"pair": pair, "count": 20})
        d = get_json("https://api.kraken.com/0/public/Depth?" + q)
        if d.get("error"):
            raise RuntimeError(",".join(d["error"]))
        result = d.get("result", {})
        key = next(iter(result))
        bids = [(float(x[0]), float(x[1])) for x in result[key].get("bids", [])]
        asks = [(float(x[0]), float(x[1])) for x in result[key].get("asks", [])]
        if not bids or not asks:
            raise RuntimeError("empty Kraken orderbook")
    except Exception as e:
        errs.append("Kraken:" + str(e))
        try:
            product = "BTC-USD" if symbol.startswith("BTC") else "ETH-USD"
            d = get_json(
                "https://api.exchange.coinbase.com/products/"
                + product
                + "/book?level=2"
            )
            bids = [(float(x[0]), float(x[1])) for x in d.get("bids", [])[:20]]
            asks = [(float(x[0]), float(x[1])) for x in d.get("asks", [])[:20]]
            if not bids or not asks:
                raise RuntimeError("empty Coinbase orderbook")
        except Exception as e2:
            errs.append("Coinbase:" + str(e2))
            raise RuntimeError("orderbook unavailable | " + " | ".join(errs))

    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2
    spread = (ask - bid) / mid * 100 if mid else 999

    bn = sum(p * q for p, q in bids)
    an = sum(p * q for p, q in asks)
    den = bn + an

    return {
        "spread_pct": spread,
        "imbalance": (bn - an) / den if den else 0.0,
    }

def fetch_derivatives(symbol):
    # Optional context only. Failure must never block paper trading.
    out = {"funding_rate": None, "open_interest": None}

    try:
        q = urllib.parse.urlencode({"symbol": symbol, "limit": 1})
        d = get_json("https://fapi.binance.com/fapi/v1/fundingRate?" + q)
        if d:
            out["funding_rate"] = float(d[-1]["fundingRate"])
    except Exception:
        pass

    try:
        q = urllib.parse.urlencode({"symbol": symbol})
        d = get_json("https://fapi.binance.com/fapi/v1/openInterest?" + q)
        out["open_interest"] = float(d["openInterest"])
    except Exception:
        pass

    return out

def ema(v, n):
    if not v:
        return []
    a = 2 / (n + 1)
    out = [float(v[0])]
    for x in v[1:]:
        out.append(a * float(x) + (1 - a) * out[-1])
    return out


def rsi(v, n=14):
    out = [50.0] * len(v)
    ag = al = 0.0
    a = 1 / n

    for i in range(1, len(v)):
        d = v[i] - v[i - 1]
        g = max(d, 0)
        l = max(-d, 0)

        if i == 1:
            ag, al = g, l
        else:
            ag = a * g + (1 - a) * ag
            al = a * l + (1 - a) * al

        out[i] = (
            100.0
            if al == 0 and ag > 0
            else (50.0 if al == 0 else 100 - 100 / (1 + ag / al))
        )

    return out


def atr(rows, n=14):
    tr = []

    for i, r in enumerate(rows):
        if i == 0:
            tr.append(r["high"] - r["low"])
        else:
            pc = rows[i - 1]["close"]
            tr.append(
                max(
                    abs(r["high"] - r["low"]),
                    abs(r["high"] - pc),
                    abs(r["low"] - pc),
                )
            )

    a = 1 / n
    out = [tr[0]]

    for x in tr[1:]:
        out.append(a * x + (1 - a) * out[-1])

    return out


def rolling_mean(v, w):
    out = [None] * len(v)
    s = 0.0

    for i, x in enumerate(v):
        s += x
        if i >= w:
            s -= v[i - w]
        if i >= w - 1:
            out[i] = s / w

    return out


def tf_view(rows):
    if len(rows) < 220:
        return {
            "regime": "unknown",
            "long": 0,
            "short": 0,
            "stop": 0.0,
            "rsi": 50.0,
            "vol_ratio": 0.0,
        }

    c = [r["close"] for r in rows]
    vol = [r["volume"] for r in rows]

    e9 = ema(c, 9)
    e20 = ema(c, 20)
    e50 = ema(c, 50)
    e200 = ema(c, 200)
    rs = rsi(c)
    at = atr(rows)
    vm = rolling_mean(vol, 20)

    r = rows[-1]
    i = len(rows) - 1
    vr = vol[-1] / vm[-1] if vm[-1] else 0

    hh = max(x["high"] for x in rows[-11:-1])
    ll = min(x["low"] for x in rows[-11:-1])

    bull = r["close"] > e50[i] > e200[i]
    bear = r["close"] < e50[i] < e200[i]
    regime = "bull" if bull else ("bear" if bear else "range")

    L = 0
    S = 0

    # Faster momentum weighting than v0.4.
    if e9[i] > e20[i]:
        L += 16
    if e20[i] > e50[i]:
        L += 16
    if r["close"] > e9[i]:
        L += 10
    if 50 <= rs[i] <= 72:
        L += 16
    if vr >= 1.05:
        L += 10
    if r["close"] > hh:
        L += 12
    if bull:
        L += 10

    if e9[i] < e20[i]:
        S += 16
    if e20[i] < e50[i]:
        S += 16
    if r["close"] < e9[i]:
        S += 10
    if 28 <= rs[i] <= 50:
        S += 16
    if vr >= 1.05:
        S += 10
    if r["close"] < ll:
        S += 12
    if bear:
        S += 10

    # Avoid chasing exhausted candles.
    if rs[i] > 80:
        L -= 16
    if rs[i] < 20:
        S -= 16

    min_stop = r["close"] * (CONFIG["min_stop_pct"] / 100.0)
    stop = max(at[i] * CONFIG["atr_stop_multiple"], min_stop)

    return {
        "regime": regime,
        "long": max(0, min(100, L)),
        "short": max(0, min(100, S)),
        "stop": stop,
        "rsi": rs[i],
        "vol_ratio": vr,
    }


def combined(tf, book, der):
    # Execution-focused weighting.
    w = {"1m": 0.45, "5m": 0.40, "15m": 0.15}

    L = sum(tf[k]["long"] * w[k] for k in w)
    S = sum(tf[k]["short"] * w[k] for k in w)

    if book["spread_pct"] > CONFIG["max_spread_pct"]:
        return {
            "action": "HOLD",
            "confidence": 0,
            "reason": "spread too wide",
            "stop": tf["1m"]["stop"],
        }

    imb = book["imbalance"]

    if imb > 0.08:
        L += 8
        S -= 3
    elif imb < -0.08:
        S += 8
        L -= 3

    fr = der.get("funding_rate")
    if fr is not None:
        if fr > 0.0008:
            L -= 5
        elif fr < -0.0008:
            S -= 5

    L = max(0, min(100, int(round(L))))
    S = max(0, min(100, int(round(S))))

    # Faster than v0.4:
    # 15m is a safety veto, not a hard trend requirement.
    long_ok = (
        tf["15m"]["regime"] != "bear"
        and tf["5m"]["regime"] in ("bull", "range")
        and tf["1m"]["long"] >= 52
    )
    short_ok = (
        tf["15m"]["regime"] != "bull"
        and tf["5m"]["regime"] in ("bear", "range")
        and tf["1m"]["short"] >= 52
    )

    if L >= CONFIG["min_confidence"] and L > S and long_ok:
        return {
            "action": "LONG",
            "confidence": L,
            "reason": "FAST long confirm",
            "stop": tf["1m"]["stop"],
        }

    if S >= CONFIG["min_confidence"] and S > L and short_ok:
        return {
            "action": "SHORT",
            "confidence": S,
            "reason": "FAST short confirm",
            "stop": tf["1m"]["stop"],
        }

    return {
        "action": "HOLD",
        "confidence": max(L, S),
        "reason": "no fast confirmation",
        "stop": tf["1m"]["stop"],
    }


def default_state():
    d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "cash": CONFIG["starting_balance_usdt"],
        "realized_pnl": 0.0,
        "positions": {},
        "closed_trades": [],
        "last_exit": {},
        "equity_peak": CONFIG["starting_balance_usdt"],
        "day_start_equity": CONFIG["starting_balance_usdt"],
        "day_key": d,
    }


def _migrate_state(s):
    """v0.5.1 P&L omitted entry fees; preserve history with audit fields."""
    if s.get("accounting_version", 1) >= 2:
        return s

    rate = CONFIG["fee_rate_pct"] / 100.0
    for trade in s.get("closed_trades", []):
        if "entry_fee" not in trade:
            old = float(trade["pnl"])
            entry_fee = abs(float(trade["qty"]) * float(trade["entry"])) * rate
            trade["legacy_reported_pnl"] = old
            trade["entry_fee"] = entry_fee
            trade["exit_fee"] = abs(float(trade["qty"]) * float(trade["exit"])) * rate
            trade["pnl"] = old - entry_fee
    for p in s.get("positions", {}).values():
        p.setdefault("entry_fee", abs(float(p["qty"]) * float(p["entry"])) * rate)

    s["realized_pnl"] = sum(float(t["pnl"]) for t in s.get("closed_trades", []))
    outstanding_entry_fees = sum(float(p["entry_fee"]) for p in s.get("positions", {}).values())
    reconciled = CONFIG["starting_balance_usdt"] + s["realized_pnl"] - outstanding_entry_fees
    discrepancy = abs(reconciled - float(s["cash"]))
    if discrepancy > 0.01:
        raise RuntimeError(
            f"State cash mismatch before migration: stored={s['cash']:.6f}, "
            f"reconciled={reconciled:.6f}; refusing automatic reset"
        )
    s["accounting_version"] = 2
    print("ACCOUNT MIGRATION | historical entry fees included; state preserved")
    return s


def load_state():
    if not STATE_FILE.exists():
        return _migrate_state(default_state())
    # Never silently reset to $100 or discard positions if state is corrupted.
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for field in ("cash", "positions", "closed_trades", "realized_pnl"):
        if field not in state:
            raise RuntimeError(f"Invalid state file: missing {field}; refusing reset")
    return _migrate_state(state)


def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    temp_path.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, STATE_FILE)


def log_event(o):
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(o) + "\n")


def unreal(p, mark):
    if p["side"] == "LONG":
        return p["qty"] * (mark - p["entry"])
    return p["qty"] * (p["entry"] - mark)


def equity(s, prices):
    return float(s["cash"]) + sum(
        unreal(p, prices.get(sym, p["entry"]))
        for sym, p in s["positions"].items()
    )


def size(balance, price, dist):
    q = min(
        balance * (CONFIG["risk_per_trade_pct"] / 100) / max(dist, 1e-12),
        (balance * 0.25) / price,
    )
    return q if q * price >= 5 else 0.0


def in_cooldown(s, sym):
    last = s.get("last_exit", {}).get(sym)
    if not last:
        return False
    mins = (datetime.now(timezone.utc) - parse_iso(last)).total_seconds() / 60.0
    return mins < CONFIG["cooldown_minutes"]


def open_pos(s, sym, side, q, price, dist, conf):
    slip = CONFIG["slippage_pct"] / 100
    fill = price * (1 + slip) if side == "LONG" else price * (1 - slip)

    stop = fill - dist if side == "LONG" else fill + dist
    tp = (
        fill + dist * CONFIG["reward_risk_ratio"]
        if side == "LONG"
        else fill - dist * CONFIG["reward_risk_ratio"]
    )

    fee = q * fill * (CONFIG["fee_rate_pct"] / 100)
    s["cash"] -= fee

    s["positions"][sym] = {
        "side": side,
        "qty": q,
        "entry": fill,
        "stop": stop,
        "tp": tp,
        "initial_dist": dist,
        "confidence": conf,
        "opened_at": now_iso(),
        "entry_fee": fee,
        # Ignore the partially formed candle containing the entry.
        "last_closed_candle_ms": int(time.time() * 1000) // 60000 * 60000,
        "lock_moved": False,
    }

    ev = {
        "type": "OPEN",
        "symbol": sym,
        "side": side,
        "qty": q,
        "entry": fill,
        "stop": stop,
        "tp": tp,
        "fee": fee,
        "time": now_iso(),
    }

    log_event(ev)
    save_state(s)
    return ev


def close_pos(s, sym, price, reason, bar_ts=None):
    p = s["positions"].get(sym)
    if not p:
        return None
    slip = CONFIG["slippage_pct"] / 100
    fill = price * (1 - slip) if p["side"] == "LONG" else price * (1 + slip)
    gross = unreal(p, fill)
    exit_fee = abs(p["qty"] * fill) * (CONFIG["fee_rate_pct"] / 100)
    entry_fee = p.get("entry_fee", abs(p["qty"] * p["entry"]) * (CONFIG["fee_rate_pct"] / 100))
    net = gross - exit_fee - entry_fee

    # Entry fee was deducted in open_pos, so deduct it only ONCE from cash.
    s["cash"] += gross - exit_fee
    s["realized_pnl"] += net
    tr = {
        "symbol": sym, "side": p["side"], "entry": p["entry"],
        "exit": fill, "qty": p["qty"], "gross_pnl": gross,
        "entry_fee": entry_fee, "exit_fee": exit_fee, "pnl": net,
        "reason": reason, "closed_at": now_iso(), "observed_bar_ms": bar_ts,
    }
    s["closed_trades"].append(tr)
    s.setdefault("last_exit", {})[sym] = now_iso()
    del s["positions"][sym]
    log_event({"type": "CLOSE", **tr})
    save_state(s)
    return tr


def maybe_profit_lock(s, sym, mark):
    p = s["positions"].get(sym)
    if not p or p.get("lock_moved"):
        return False

    dist = p["initial_dist"]
    trigger = dist * CONFIG["profit_lock_trigger_r"]

    # Cover most simulated round-trip cost once momentum has moved enough.
    cost_pct = (
        2 * (CONFIG["fee_rate_pct"] + CONFIG["slippage_pct"]) + 0.03
    ) / 100.0

    if p["side"] == "LONG":
        favorable = mark - p["entry"]
        if favorable >= trigger:
            new_stop = p["entry"] * (1 + cost_pct)
            if new_stop < p["tp"]:
                p["stop"] = max(p["stop"], new_stop)
                p["lock_moved"] = True
                log_event({
                    "type": "PROFIT_LOCK",
                    "symbol": sym,
                    "side": p["side"],
                    "new_stop": p["stop"],
                    "time": now_iso(),
                })
                save_state(s)
                return True

    else:
        favorable = p["entry"] - mark
        if favorable >= trigger:
            new_stop = p["entry"] * (1 - cost_pct)
            if new_stop > p["tp"]:
                p["stop"] = min(p["stop"], new_stop)
                p["lock_moved"] = True
                log_event({
                    "type": "PROFIT_LOCK",
                    "symbol": sym,
                    "side": p["side"],
                    "new_stop": p["stop"],
                    "time": now_iso(),
                })
                save_state(s)
                return True

    return False


def stats(s):
    t = s["closed_trades"]
    wins = [x for x in t if x["pnl"] > 0]
    loss = [x for x in t if x["pnl"] <= 0]

    gp = sum(x["pnl"] for x in wins)
    gl = -sum(x["pnl"] for x in loss)

    pf = gp / gl if gl > 0 else (999 if gp > 0 else 0)
    wr = len(wins) / len(t) * 100 if t else 0

    return len(t), wr, pf


def manage_position(s, sym, exec_rows):
    """Replay available post-entry 1m bars across GitHub scheduling gaps.

    Entry-minute bars are skipped (their high/low may predate our fill).
    SL wins when TP and SL both touch in the same 1m candle, and gap opens
    through an SL get the worse opening fill. This is an approximation,
    never an exchange-hosted stop order.
    """
    p = s["positions"].get(sym)
    if not p:
        return None
    if not exec_rows:
        raise RuntimeError("Position open but 1-minute market data unavailable")

    opened_ms = int(parse_iso(p["opened_at"]).timestamp() * 1000)
    first_full_minute = (opened_ms // 60000 + 1) * 60000
    seen = int(p.get("last_closed_candle_ms", first_full_minute - 60000))
    if seen < first_full_minute - 60000:
        seen = first_full_minute - 60000

    expiry = opened_ms + CONFIG["max_hold_minutes"] * 60000
    eligible = [r for r in exec_rows if int(r["timestamp"]) >= first_full_minute
                and int(r["timestamp"]) > seen]
    if not eligible:
        if int(time.time() * 1000) >= expiry:
            # No reliable historical candles: flag an unverified exit price.
            raise RuntimeError(f"{sym} cannot verify expired paper position; preserve state")
        return None

    if int(eligible[0]["timestamp"]) - seen > 60000:
        raise RuntimeError(f"{sym} missing 1m candles across gap; preserve position for review")

    for i, bar in enumerate(eligible):
        ts = int(bar["timestamp"])
        o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
        last_forming = ts == int(exec_rows[-1]["timestamp"])
        stop, target = float(p["stop"]), float(p["tp"])

        if p["side"] == "LONG":
            stop_hit = l <= stop
            tp_hit = h >= target
            stop_fill = min(stop, o)  # adverse gap through stop
        else:
            stop_hit = h >= stop
            tp_hit = l <= target
            stop_fill = max(stop, o)  # adverse gap through stop

        # With OHLC bars the order of intraminute touches is unknowable.
        if stop_hit:
            return close_pos(s, sym, stop_fill, "STOP_CONSERVATIVE", ts)
        if tp_hit:
            return close_pos(s, sym, target, "TAKE_PROFIT", ts)
        if ts >= expiry:
            price = float(bar["close"]) if last_forming else o
            return close_pos(s, sym, price, "TIME_EXIT_CATCHUP", ts)
        if not last_forming:
            p["last_closed_candle_ms"] = ts
    # Profit-lock disabled under intermittently scheduled OHLC simulation:
    # replaying candle highs/lows after changing a stop would invent chronology.
    return None


def run_cycle(s):
    prices = {}
    healthy_symbols = 0

    for sym in CONFIG["symbols"]:
        try:
            tf = {}
            exec_rows = None

            for k in CONFIG["timeframes"]:
                rows, src = fetch_ohlcv(sym, k, CONFIG["ohlcv_limit"])
                tf[k] = tf_view(rows)

                if k == "1m":
                    exec_rows = rows

            # Reject stale candles before marking any paper position.
            age_ms = time.time() * 1000 - exec_rows[-1]["timestamp"]
            if age_ms > 180000 or age_ms < -60000:
                raise RuntimeError(f"Stale or future 1m candle for {sym}: age={age_ms/1000:.1f}s")

            px = exec_rows[-1]["close"]
            prices[sym] = px

            eq = equity(s, prices)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            if s.get("day_key") != today:
                s["day_key"] = today
                s["day_start_equity"] = eq

            tr = manage_position(s, sym, exec_rows)
            if tr:
                print(
                    f"{sym} CLOSE {tr['side']} {tr['reason']} "
                    f"pnl={tr['pnl']:.4f}"
                )

            # Failed depth/funding must NOT prevent an open position's exit checks.
            book = fetch_orderbook(sym)
            der = fetch_derivatives(sym)
            healthy_symbols += 1
            sig = combined(tf, book, der)

            eq = equity(s, prices)
            s["equity_peak"] = max(float(s.get("equity_peak", eq)), eq)

            dd = (
                (s["equity_peak"] - eq) / s["equity_peak"] * 100
                if s["equity_peak"]
                else 0
            )

            day0 = float(s.get("day_start_equity", eq))
            dl = max(0, (day0 - eq) / day0 * 100) if day0 else 100

            print(
                f"{sym} | {px:.2f} | {sig['action']} conf={sig['confidence']} "
                f"| spread={book['spread_pct']:.4f}% "
                f"| book={book['imbalance']:+.2f}"
            )
            print(
                f"  1m={tf['1m']['regime']} "
                f"5m={tf['5m']['regime']} "
                f"15m={tf['15m']['regime']} "
                f"| RSI1m={tf['1m']['rsi']:.1f} "
                f"| funding={der.get('funding_rate')} "
                f"| OI={der.get('open_interest')}"
            )

            if dl >= CONFIG["max_daily_loss_pct"]:
                print(f"  KILL SWITCH daily loss {dl:.2f}%")
                continue

            if dd >= CONFIG["max_total_drawdown_pct"]:
                print(f"  KILL SWITCH drawdown {dd:.2f}%")
                continue

            if in_cooldown(s, sym):
                print("  COOLDOWN after recent exit")
                continue

            if (
                CONFIG["entry_enabled"]
                and sig["action"] in ("LONG", "SHORT")
                and sym not in s["positions"]
                and len(s["positions"]) < CONFIG["max_open_positions"]
            ):
                q = size(eq, px, sig["stop"])

                if q > 0:
                    ev = open_pos(
                        s,
                        sym,
                        sig["action"],
                        q,
                        px,
                        sig["stop"],
                        sig["confidence"],
                    )
                    print(
                        f"  PAPER OPEN {ev['side']} "
                        f"qty={ev['qty']:.8f} "
                        f"entry={ev['entry']:.2f} "
                        f"stop={ev['stop']:.2f} "
                        f"tp={ev['tp']:.2f}"
                    )

        except Exception as e:
            print(f"{sym} ERROR {type(e).__name__}: {e}")

    eq = equity(s, prices)
    n, wr, pf = stats(s)

    print(
        f"ACCOUNT | equity={eq:.4f} "
        f"| realized={s['realized_pnl']:.4f} "
        f"| closed={n} "
        f"| win={wr:.1f}% "
        f"| PF={pf:.2f}"
    )

    save_state(s)
    if not CONFIG["entry_enabled"]:
        print("SAFETY PAUSE | new paper entries disabled pending backtest")
    return healthy_symbols


def smoke_test():
    random.seed(42)
    rows = []
    p = 100.0

    for i in range(500):
        o = p
        p = max(1, p * math.exp(random.gauss(0.0002, 0.006)))
        h = max(o, p) * (1 + random.random() * 0.004)
        l = min(o, p) * (1 - random.random() * 0.004)

        rows.append(
            {
                "timestamp": i,
                "open": o,
                "high": h,
                "low": l,
                "close": p,
                "volume": 100 + random.random() * 200,
            }
        )

    v = tf_view(rows)

    assert v["regime"] in ("bull", "bear", "range")
    assert v["stop"] > 0

    fake_tf = {"1m": v, "5m": v, "15m": v}
    fake_book = {"spread_pct": 0.01, "imbalance": 0.15}
    fake_der = {"funding_rate": 0.0, "open_interest": 1.0}
    sig = combined(fake_tf, fake_book, fake_der)

    assert sig["action"] in ("LONG", "SHORT", "HOLD")

    print("SMOKE TEST PASSED")
    print("VERSION:", VERSION)
    print("TF:", v)
    print("SIGNAL:", sig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--cycles", type=int, default=0,
                    help="Run N scan cycles then exit; 0 = continuous.")
    a = ap.parse_args()

    if a.test:
        smoke_test()
        return

    if not CONFIG["paper_only"]:
        raise RuntimeError("PAPER ONLY")

    s = load_state()

    if a.once:
        if run_cycle(s) == 0:
            raise SystemExit("FAIL: no usable market data on this run")
        return

    if a.cycles > 0:
        print(f"RUDRILA Crypto AI v0.5 FAST SCALP PAPER: {a.cycles} cloud cycles.")
        good = 0
        for i in range(a.cycles):
            print(f"--- cycle {i+1}/{a.cycles} ---")
            good += run_cycle(s)
            if i + 1 < a.cycles:
                time.sleep(CONFIG["poll_seconds"])
        if good == 0:
            raise SystemExit("FAIL: zero healthy symbol-scans; no false green check")
        return

    print(
        "RUDRILA Crypto AI v0.5 FAST SCALP running in PAPER mode. "
        "Ctrl+C to stop."
    )

    while True:
        run_cycle(s)
        time.sleep(CONFIG["poll_seconds"])


if __name__ == "__main__":
    main()
