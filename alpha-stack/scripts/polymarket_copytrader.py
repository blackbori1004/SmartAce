#!/usr/bin/env python3
import argparse
import base64
import binascii
import json
import os
import time
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = STATE_DIR / "polymarket_copy_state.json"
LOG_PATH = STATE_DIR / "polymarket_copy_log.jsonl"
ENV_PATH = ROOT / ".env.polymarket"
DATA_API = "https://data-api.polymarket.com/trades"


def _looks_base64(s: str) -> bool:
    try:
        base64.b64decode(s, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def load_state() -> Dict:
    if STATE_PATH.exists():
        st = json.loads(STATE_PATH.read_text())
        st.setdefault("seen", {})
        st.setdefault("positions", {})
        return st
    return {"seen": {}, "positions": {}}


def save_state(st: Dict) -> None:
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def log_event(evt: Dict) -> None:
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")


def fetch_user_trades(user: str, limit: int = 20) -> List[Dict]:
    r = requests.get(DATA_API, params={"user": user, "limit": limit, "offset": 0}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def build_client() -> ClobClient:
    load_dotenv(ENV_PATH)
    host = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com").strip()
    chain_id = int(os.getenv("POLYMARKET_CHAIN_ID", "137").strip())
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()
    funder = os.getenv("POLYMARKET_FUNDER", "").strip()
    sig_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0").strip())
    if not pk or not funder:
        raise RuntimeError("Missing POLYMARKET_PRIVATE_KEY/POLYMARKET_FUNDER in .env.polymarket")

    client = ClobClient(host, key=pk, chain_id=chain_id, signature_type=sig_type, funder=funder)

    k = os.getenv("POLYMARKET_API_KEY", "").strip()
    s = os.getenv("POLYMARKET_API_SECRET", "").strip()
    p = os.getenv("POLYMARKET_API_PASSPHRASE", "").strip()
    if k and s and p and _looks_base64(s):
        client.set_api_creds(ApiCreds(api_key=k, api_secret=s, api_passphrase=p))
    else:
        client.set_api_creds(client.create_or_derive_api_creds())
    return client


def trade_key(t: Dict) -> str:
    return "|".join(
        [
            str(t.get("transactionHash") or ""),
            str(t.get("asset") or ""),
            str(t.get("side") or ""),
            str(t.get("size") or ""),
            str(t.get("timestamp") or ""),
        ]
    )


def maybe_close_positions(
    client: ClobClient,
    positions: Dict[str, Dict],
    tp_pct: float,
    sl_pct: float,
    max_hold_minutes: int,
) -> int:
    now = int(time.time())
    closed = 0

    for asset, p in list(positions.items()):
        try:
            qty = float(p.get("qty", 0) or 0)
            entry = float(p.get("entry_price", 0) or 0)
            opened_ts = int(p.get("opened_ts", now) or now)
            if qty <= 0 or entry <= 0:
                continue

            last_px = float(client.get_last_trade_price(asset) or 0)
            if last_px <= 0:
                continue

            tp_px = entry * (1 + tp_pct / 100.0)
            sl_px = entry * (1 - sl_pct / 100.0)
            timed_out = max_hold_minutes > 0 and opened_ts < now - max_hold_minutes * 60

            reason = None
            if last_px >= tp_px:
                reason = "tp"
            elif last_px <= sl_px:
                reason = "sl"
            elif timed_out:
                reason = "time"

            if not reason:
                continue

            mo = MarketOrderArgs(token_id=asset, amount=qty, side=SELL)
            signed = client.create_market_order(mo)
            res = client.post_order(signed, OrderType.FOK)

            evt = {
                "mode": "CLOSE",
                "asset": asset,
                "slug": p.get("slug"),
                "title": p.get("title"),
                "reason": reason,
                "entry_price": entry,
                "last_price": last_px,
                "qty": qty,
                "opened_ts": opened_ts,
                "closed_ts": now,
                "result": res,
                "ts": now,
            }
            log_event(evt)
            positions.pop(asset, None)
            closed += 1
        except Exception as e:
            log_event({"mode": "CLOSE_ERROR", "asset": asset, "error": str(e), "ts": int(time.time())})

    return closed


def bootstrap_positions_from_log(positions: Dict[str, Dict]) -> Dict[str, Dict]:
    if positions or not LOG_PATH.exists():
        return positions

    out = {}
    for ln in LOG_PATH.read_text().strip().splitlines():
        try:
            x = json.loads(ln)
        except Exception:
            continue
        m = x.get("mode")
        if m == "EXECUTE":
            res = x.get("result") or {}
            if str(res.get("status")) != "matched":
                continue
            asset = str(x.get("asset") or "")
            qty = float(res.get("takingAmount") or 0)
            cost = float(res.get("makingAmount") or x.get("my_usd") or 0)
            if not asset or qty <= 0:
                continue
            entry = cost / qty
            old = out.get(asset)
            if old:
                oq = float(old.get("qty", 0))
                oe = float(old.get("entry_price", 0))
                nq = oq + qty
                ne = ((oq * oe) + (qty * entry)) / nq if nq > 0 else entry
                old["qty"] = nq
                old["entry_price"] = ne
                old["updated_ts"] = int(x.get("ts") or time.time())
            else:
                out[asset] = {
                    "asset": asset,
                    "slug": x.get("slug"),
                    "title": x.get("title"),
                    "qty": qty,
                    "entry_price": entry,
                    "opened_ts": int(x.get("ts") or time.time()),
                    "updated_ts": int(x.get("ts") or time.time()),
                }
        elif m == "CLOSE":
            asset = str(x.get("asset") or "")
            qty = float(x.get("qty") or 0)
            if asset in out:
                out[asset]["qty"] = max(0.0, float(out[asset].get("qty", 0)) - qty)
                if out[asset]["qty"] <= 0:
                    out.pop(asset, None)

    return out


def run_once(
    whales: List[str],
    usd_scale: float,
    usd_cap: float,
    min_whale_cash: float,
    execute: bool,
    max_actions: int,
    max_total_usd: float,
    max_age_minutes: int,
    tp_pct: float,
    sl_pct: float,
    max_hold_minutes: int,
) -> None:
    st = load_state()
    seen = st.get("seen", {})
    positions = bootstrap_positions_from_log(st.get("positions", {}))
    client = build_client() if execute else None

    closed_count = 0
    if execute and client:
        closed_count = maybe_close_positions(client, positions, tp_pct=tp_pct, sl_pct=sl_pct, max_hold_minutes=max_hold_minutes)

    now = int(time.time())
    candidates = []
    consensus: Dict[str, set] = {}

    for w in whales:
        trades = fetch_user_trades(w, limit=30)
        for t in reversed(trades):
            k = trade_key(t)
            if seen.get(k):
                continue

            ts_raw = int(t.get("timestamp") or 0)
            if max_age_minutes > 0 and ts_raw > 0 and ts_raw < now - max_age_minutes * 60:
                continue

            side = (t.get("side") or "").upper()
            if side != "BUY":
                continue

            asset = str(t.get("asset") or "")
            price = float(t.get("price") or 0)
            size = float(t.get("size") or 0)
            whale_cash = price * size
            if not asset or whale_cash < min_whale_cash:
                continue

            seen[k] = now
            consensus.setdefault(asset, set()).add(w)
            candidates.append(
                {
                    "k": k,
                    "whale": w,
                    "title": t.get("title"),
                    "slug": t.get("slug"),
                    "asset": asset,
                    "side": side,
                    "price": price,
                    "whale_cash": whale_cash,
                }
            )

    # 고래 합의(동일 asset 동시 매수) + 승률(시장암묵확률=price) 가중치
    for c in candidates:
        base_usd = min(usd_cap, max(1.0, c["whale_cash"] * usd_scale))
        whale_count = len(consensus.get(c["asset"], set()))
        consensus_weight = min(2.2, 1.0 + 0.40 * (whale_count - 1))
        prob_weight = min(1.6, max(0.7, 0.6 + 0.8 * c["price"]))
        weighted_usd = min(usd_cap, base_usd * consensus_weight * prob_weight)

        c["whale_count"] = whale_count
        c["consensus_weight"] = round(consensus_weight, 3)
        c["prob_weight"] = round(prob_weight, 3)
        c["my_usd"] = round(weighted_usd, 4)

    # 강한 합의/가중치 순으로 실행
    candidates.sort(key=lambda x: (x["whale_count"], x["my_usd"], x["whale_cash"]), reverse=True)

    actions = []
    total_usd = 0.0
    for c in candidates:
        my_usd = float(c["my_usd"])
        if total_usd + my_usd > max_total_usd:
            continue

        plan = {
            "whale": c["whale"],
            "title": c["title"],
            "slug": c["slug"],
            "asset": c["asset"],
            "side": c["side"],
            "whale_cash": round(c["whale_cash"], 4),
            "my_usd": round(my_usd, 4),
            "price": c["price"],
            "whale_count": c["whale_count"],
            "consensus_weight": c["consensus_weight"],
            "prob_weight": c["prob_weight"],
            "ts": int(time.time()),
        }

        if execute:
            mo = MarketOrderArgs(token_id=c["asset"], amount=my_usd, side=BUY)
            signed = client.create_market_order(mo)
            res = client.post_order(signed, OrderType.FOK)
            plan["result"] = res
            plan["mode"] = "EXECUTE"

            if (res or {}).get("status") == "matched":
                qty = float(res.get("takingAmount") or 0)
                cost = float(res.get("makingAmount") or my_usd)
                if qty > 0:
                    entry = cost / qty
                    old = positions.get(c["asset"])
                    if old:
                        old_qty = float(old.get("qty", 0) or 0)
                        old_entry = float(old.get("entry_price", 0) or 0)
                        new_qty = old_qty + qty
                        new_entry = ((old_qty * old_entry) + (qty * entry)) / new_qty if new_qty > 0 else entry
                        positions[c["asset"]] = {
                            **old,
                            "qty": new_qty,
                            "entry_price": new_entry,
                            "updated_ts": int(time.time()),
                        }
                    else:
                        positions[c["asset"]] = {
                            "asset": c["asset"],
                            "slug": c.get("slug"),
                            "title": c.get("title"),
                            "qty": qty,
                            "entry_price": entry,
                            "opened_ts": int(time.time()),
                            "updated_ts": int(time.time()),
                        }
        else:
            plan["mode"] = "DRY_RUN"

        actions.append(plan)
        total_usd += my_usd
        log_event(plan)

        if len(actions) >= max_actions:
            break

    st["seen"] = seen
    st["positions"] = positions
    save_state(st)
    print(
        json.dumps(
            {
                "ok": True,
                "actions": len(actions),
                "closed": closed_count,
                "execute": execute,
                "total_usd": round(total_usd, 4),
            },
            ensure_ascii=False,
        )
    )
    for a in actions[:10]:
        print(json.dumps(a, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description="Polymarket whale copy trader (MVP)")
    ap.add_argument("--whales", required=True, help="comma separated whale addresses")
    ap.add_argument("--usd-scale", type=float, default=0.2, help="copy size factor vs whale cash")
    ap.add_argument("--usd-cap", type=float, default=25.0, help="max USD per copied trade")
    ap.add_argument("--min-whale-cash", type=float, default=50.0, help="ignore tiny whale trades")
    ap.add_argument("--loop", action="store_true", help="run continuously")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--execute", action="store_true", help="actually place orders")
    ap.add_argument("--max-actions", type=int, default=1, help="max copied trades per run")
    ap.add_argument("--max-total-usd", type=float, default=10.0, help="max total USD copied per run")
    ap.add_argument("--max-age-minutes", type=int, default=120, help="copy only recent whale trades (0=disable)")
    ap.add_argument("--tp-pct", type=float, default=12.0, help="take-profit percent for copied position")
    ap.add_argument("--sl-pct", type=float, default=8.0, help="stop-loss percent for copied position")
    ap.add_argument("--max-hold-minutes", type=int, default=180, help="force close after hold time")
    args = ap.parse_args()

    whales = [x.strip() for x in args.whales.split(",") if x.strip()]
    if not whales:
        raise RuntimeError("No whale addresses provided")

    if args.loop:
        while True:
            try:
                run_once(
                    whales,
                    args.usd_scale,
                    args.usd_cap,
                    args.min_whale_cash,
                    args.execute,
                    args.max_actions,
                    args.max_total_usd,
                    args.max_age_minutes,
                    args.tp_pct,
                    args.sl_pct,
                    args.max_hold_minutes,
                )
            except Exception as e:
                print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            time.sleep(args.interval)
    else:
        run_once(
            whales,
            args.usd_scale,
            args.usd_cap,
            args.min_whale_cash,
            args.execute,
            args.max_actions,
            args.max_total_usd,
            args.max_age_minutes,
            args.tp_pct,
            args.sl_pct,
            args.max_hold_minutes,
        )


if __name__ == "__main__":
    main()
