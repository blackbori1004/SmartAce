#!/usr/bin/env python3
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.polymarket"


def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def build_client() -> ClobClient:
    host = _getenv("POLYMARKET_HOST", "https://clob.polymarket.com")
    chain_id = int(_getenv("POLYMARKET_CHAIN_ID", "137"))
    pk = _getenv("POLYMARKET_PRIVATE_KEY")
    funder = _getenv("POLYMARKET_FUNDER")
    sig_type = int(_getenv("POLYMARKET_SIGNATURE_TYPE", "0"))

    if not pk:
        raise RuntimeError("POLYMARKET_PRIVATE_KEY is required")
    if not funder:
        raise RuntimeError("POLYMARKET_FUNDER is required")

    client = ClobClient(host, key=pk, chain_id=chain_id, signature_type=sig_type, funder=funder)

    api_key = _getenv("POLYMARKET_API_KEY")
    api_secret = _getenv("POLYMARKET_API_SECRET")
    api_pass = _getenv("POLYMARKET_API_PASSPHRASE")

    if api_key and api_secret and api_pass:
        client.set_api_creds({"key": api_key, "secret": api_secret, "passphrase": api_pass})
        mode = "provided-api-creds"
    else:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        mode = "created-or-derived-api-creds"

    setattr(client, "_auth_mode", mode)
    return client


def main() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)

    client = build_client()

    out = {
        "host": _getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
        "chain_id": int(_getenv("POLYMARKET_CHAIN_ID", "137")),
        "funder": _getenv("POLYMARKET_FUNDER"),
        "signature_type": int(_getenv("POLYMARKET_SIGNATURE_TYPE", "0")),
        "auth_mode": getattr(client, "_auth_mode", "unknown"),
        "ok": client.get_ok(),
    }

    # private endpoints sanity check
    try:
        orders = client.get_orders()
        out["open_orders_count"] = len(orders) if isinstance(orders, list) else None
    except Exception as e:
        out["open_orders_error"] = str(e)

    try:
        trades = client.get_trades()
        out["recent_trades_count"] = len(trades) if isinstance(trades, list) else None
    except Exception as e:
        out["recent_trades_error"] = str(e)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
