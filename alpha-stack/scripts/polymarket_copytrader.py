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
from py_clob_client.order_builder.constants import BUY

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
        return json.loads(STATE_PATH.read_text())
    return {"seen": {}}


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


def run_once(whales: List[str], usd_scale: float, usd_cap: float, min_whale_cash: float, execute: bool) -> None:
    st = load_state()
    seen = st.get("seen", {})
    client = build_client() if execute else None

    actions = []
    for w in whales:
        trades = fetch_user_trades(w, limit=30)
        for t in reversed(trades):
            k = trade_key(t)
            if seen.get(k):
                continue
            seen[k] = int(time.time())

            side = (t.get("side") or "").upper()
            if side != "BUY":
                continue  # MVP: buy-copy only (sell-copy는 포지션/재고 동기화 필요)

            asset = str(t.get("asset") or "")
            price = float(t.get("price") or 0)
            size = float(t.get("size") or 0)
            whale_cash = price * size
            if not asset or whale_cash < min_whale_cash:
                continue

            my_usd = min(usd_cap, max(1.0, whale_cash * usd_scale))
            plan = {
                "whale": w,
                "title": t.get("title"),
                "slug": t.get("slug"),
                "asset": asset,
                "side": side,
                "whale_cash": round(whale_cash, 4),
                "my_usd": round(my_usd, 4),
                "price": price,
                "ts": int(time.time()),
            }

            if execute:
                mo = MarketOrderArgs(token_id=asset, amount=my_usd, side=BUY)
                signed = client.create_market_order(mo)
                res = client.post_order(signed, OrderType.FOK)
                plan["result"] = res
                plan["mode"] = "EXECUTE"
            else:
                plan["mode"] = "DRY_RUN"

            actions.append(plan)
            log_event(plan)

    st["seen"] = seen
    save_state(st)
    print(json.dumps({"ok": True, "actions": len(actions), "execute": execute}, ensure_ascii=False))
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
    args = ap.parse_args()

    whales = [x.strip() for x in args.whales.split(",") if x.strip()]
    if not whales:
        raise RuntimeError("No whale addresses provided")

    if args.loop:
        while True:
            try:
                run_once(whales, args.usd_scale, args.usd_cap, args.min_whale_cash, args.execute)
            except Exception as e:
                print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            time.sleep(args.interval)
    else:
        run_once(whales, args.usd_scale, args.usd_cap, args.min_whale_cash, args.execute)


if __name__ == "__main__":
    main()
