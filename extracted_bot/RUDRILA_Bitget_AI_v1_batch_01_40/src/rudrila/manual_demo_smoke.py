import json, time, uuid
from rudrila.settings import BitgetSettings, load_config
from rudrila.runtime_engine import DemoTradingRuntime
from rudrila.rest_client import normalize_qty

def jprint(tag, obj):
    print(tag + " " + json.dumps(obj, separators=(",", ":"), default=str), flush=True)

def main():
    s = BitgetSettings.from_env()
    if s.mode != "demo" or s.live_trading:
        raise RuntimeError("MANUAL_SMOKE_REFUSED: DEMO mode required and LIVE_TRADING must be false")
    s.require_demo_credentials()
    c = load_config()
    rt = DemoTradingRuntime(s, c)
    try:
        eq = rt._equity_from_private(force=True)
        rt._refresh_account_meta(force=True)
        jprint("MANUAL_SMOKE_PREFLIGHT", {
            "mode": s.mode,
            "live_trading": s.live_trading,
            "backend": rt.execution_backend,
            "equity_positive": bool(eq > 0),
            "hold_mode": rt.account_hold_mode,
            "target_leverage": rt.target_leverage
        })
        if eq <= 0:
            raise RuntimeError("MANUAL_SMOKE_NO_DEMO_EQUITY")
        if rt.execution_backend != "CLASSIC_V2_DEMO":
            raise RuntimeError("MANUAL_SMOKE_ABORT: expected CLASSIC_V2_DEMO for this test")
        if not rt._configure_demo_leverage(force=True):
            raise RuntimeError("MANUAL_SMOKE_LEVERAGE_NOT_READY: " + rt.leverage_error)

        sym = "ETHUSDT"
        inst_raw = rt.rest.instruments(sym).get("data")
        if isinstance(inst_raw, list):
            inst = next((x for x in inst_raw if str(x.get("symbol","")).upper() == sym), inst_raw[0] if inst_raw else {})
        elif isinstance(inst_raw, dict):
            nested = inst_raw.get("list") or inst_raw.get("symbols")
            if isinstance(nested, list):
                inst = next((x for x in nested if str(x.get("symbol","")).upper() == sym), nested[0] if nested else {})
            else:
                inst = inst_raw
        else:
            inst = {}

        ob = rt.rest.orderbook(sym, 5).get("data") or {}
        bids = ob.get("bids") or []
        asks = ob.get("asks") or []
        bid = float(bids[0][0]) if bids else 0.0
        ask = float(asks[0][0]) if asks else 0.0
        mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else max(bid, ask)
        if mid <= 0:
            raise RuntimeError("MANUAL_SMOKE_NO_MARKET_PRICE")

        min_amt = float(inst.get("minOrderAmount") or inst.get("minTradeUSDT") or 0)
        min_qty = float(inst.get("minOrderQty") or inst.get("minTradeNum") or 0)
        target_notional = max(10.0, min_amt * 1.25)
        raw_qty = max(target_notional / mid, min_qty * 1.25 if min_qty > 0 else 0.0)
        qty = normalize_qty(raw_qty, inst)
        if qty <= 0:
            qty = normalize_qty(max(0.01, min_qty), inst)
        if qty <= 0:
            raise RuntimeError("MANUAL_SMOKE_QTY_NORMALIZATION_FAILED")

        oid = "RUD-MANUAL-" + str(int(time.time()*1000)) + "-" + uuid.uuid4().hex[:6]
        tp = mid * 1.01
        sl = mid * 0.99
        body = rt.exec.build_classic_order(
            sym, "buy", qty, order_type="market", oid=oid,
            margin_coin=rt.demo_margin_coin, take_profit=tp, stop_loss=sl
        )
        ack = rt.rest.classic_place_order(body)
        jprint("MANUAL_SMOKE_OPEN_ACK", {
            "code": ack.get("code"), "msg": ack.get("msg"),
            "orderId": (ack.get("data") or {}).get("orderId"),
            "clientOid": (ack.get("data") or {}).get("clientOid"),
            "symbol": sym, "qty": qty, "mid": mid
        })

        time.sleep(2.5)
        rows = rt.rest.classic_positions(margin_coin=rt.demo_margin_coin).get("data") or []
        pos = []
        for x in rows:
            if isinstance(x, dict) and rt._same_market(x.get("symbol"), sym):
                sz = float(x.get("total") or x.get("available") or 0)
                if sz > 0:
                    pos.append((x, sz))
        jprint("MANUAL_SMOKE_POSITION", {
            "found": bool(pos),
            "positions": [{"symbol": x.get("symbol"), "holdSide": x.get("holdSide"), "size": sz} for x,sz in pos]
        })
        if not pos:
            raise RuntimeError("MANUAL_SMOKE_ORDER_ACK_BUT_NO_OPEN_POSITION")

        mode = str(rt.account_hold_mode or "").lower()
        close_errors = []
        close_ack = None
        for x, sz in pos:
            hold = str(x.get("holdSide") or "").lower()
            attempts = []
            if "hedge" in mode:
                hside = "buy" if hold == "long" else "sell" if hold == "short" else "buy"
                attempts.append({
                    "symbol": sym, "productType": "USDT-FUTURES", "marginMode": "crossed",
                    "marginCoin": rt.demo_margin_coin, "size": format(sz, ".12g"),
                    "side": hside, "tradeSide": "close", "orderType": "market", "force": "gtc",
                    "clientOid": "RUD-CLOSE-" + str(int(time.time()*1000)) + "-" + uuid.uuid4().hex[:6]
                })
            else:
                oside = "sell" if hold in ("long","") else "buy"
                attempts.append({
                    "symbol": sym, "productType": "USDT-FUTURES", "marginMode": "crossed",
                    "marginCoin": rt.demo_margin_coin, "size": format(sz, ".12g"),
                    "side": oside, "orderType": "market", "force": "gtc", "reduceOnly": "YES",
                    "clientOid": "RUD-CLOSE-" + str(int(time.time()*1000)) + "-" + uuid.uuid4().hex[:6]
                })
                hside = "buy" if hold == "long" else "sell" if hold == "short" else "buy"
                attempts.append({
                    "symbol": sym, "productType": "USDT-FUTURES", "marginMode": "crossed",
                    "marginCoin": rt.demo_margin_coin, "size": format(sz, ".12g"),
                    "side": hside, "tradeSide": "close", "orderType": "market", "force": "gtc",
                    "clientOid": "RUD-CLOSE-" + str(int(time.time()*1000)) + "-" + uuid.uuid4().hex[:6]
                })
            for cb in attempts:
                try:
                    close_ack = rt.rest.classic_place_order(cb)
                    break
                except Exception as exc:
                    close_errors.append(str(exc))
            if close_ack is not None:
                break

        if close_ack is None:
            raise RuntimeError("MANUAL_SMOKE_CLOSE_FAILED: " + " | ".join(close_errors[-3:]))

        jprint("MANUAL_SMOKE_CLOSE_ACK", {
            "code": close_ack.get("code"), "msg": close_ack.get("msg"),
            "orderId": (close_ack.get("data") or {}).get("orderId"),
            "clientOid": (close_ack.get("data") or {}).get("clientOid")
        })
        time.sleep(2.5)
        after_rows = rt.rest.classic_positions(margin_coin=rt.demo_margin_coin).get("data") or []
        after = []
        for x in after_rows:
            if isinstance(x, dict) and rt._same_market(x.get("symbol"), sym):
                sz = float(x.get("total") or x.get("available") or 0)
                if sz > 0:
                    after.append({"symbol": x.get("symbol"), "holdSide": x.get("holdSide"), "size": sz})

        jprint("MANUAL_SMOKE_RESULT", {
            "pass": len(after) == 0,
            "http400_fixed": True,
            "open_ack": True,
            "position_seen": True,
            "close_ack": True,
            "remaining_positions": after
        })
        if after:
            raise RuntimeError("MANUAL_SMOKE_CLOSE_ACK_BUT_POSITION_REMAINS")
    finally:
        try:
            rt.journal.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
