#!/usr/bin/env python3
import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)
RISK_PATH = STATE_DIR / "risk_state.json"
LOG_PATH = STATE_DIR / "fills.jsonl"
KILL_SWITCH = Path.home() / ".openclaw" / "workspace" / ".pi" / "hyperliquid.pause"


@dataclass
class RiskConfig:
    max_notional_usd: float = float(os.getenv("HL_MAX_NOTIONAL_USD", "100"))
    max_daily_loss_pct: float = float(os.getenv("HL_MAX_DAILY_LOSS_PCT", "3"))
    max_slippage: float = float(os.getenv("HL_MAX_SLIPPAGE", "0.003"))
    max_open_positions: int = int(os.getenv("HL_MAX_OPEN_POSITIONS", "1"))


def _load_key() -> str:
    key = os.getenv("HYPERLIQUID_PRIVATE_KEY", "").strip()
    if not key:
        raise RuntimeError("HYPERLIQUID_PRIVATE_KEY not set")
    if key.startswith("0x") and len(key) == 42:
        raise RuntimeError("HYPERLIQUID_PRIVATE_KEY looks like a wallet address, not a private key")
    return key


def _address_only() -> str:
    # Fallback order: explicit account -> legacy api_key-as-address -> derived from key
    if os.getenv("HL_ACCOUNT_ADDRESS", "").strip():
        return os.getenv("HL_ACCOUNT_ADDRESS", "").strip()
    if os.getenv("HYPERLIQUID_API_KEY", "").strip().startswith("0x"):
        return os.getenv("HYPERLIQUID_API_KEY", "").strip()
    key = os.getenv("HYPERLIQUID_PRIVATE_KEY", "").strip()
    if key:
        try:
            return Account.from_key(key).address
        except Exception:
            pass
    raise RuntimeError("Set HL_ACCOUNT_ADDRESS (or valid HYPERLIQUID_PRIVATE_KEY)")


def _wallet_and_address() -> tuple[Any, str]:
    key = _load_key()
    acct = Account.from_key(key)
    addr = os.getenv("HL_ACCOUNT_ADDRESS", acct.address)
    return acct, addr


def _load_risk_state() -> Dict[str, Any]:
    if not RISK_PATH.exists():
        return {
            "day": time.strftime("%Y-%m-%d"),
            "start_value": None,
            "daily_realized_pnl": 0.0,
            "last_order_ts": None,
        }
    return json.loads(RISK_PATH.read_text())


def _save_risk_state(st: Dict[str, Any]) -> None:
    RISK_PATH.write_text(json.dumps(st, indent=2))


def _log(event: Dict[str, Any]) -> None:
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _setup() -> tuple[Info, Exchange, str, RiskConfig]:
    wallet, addr = _wallet_and_address()
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exch = Exchange(wallet, constants.MAINNET_API_URL)
    return info, exch, addr, RiskConfig()


def show_status() -> None:
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    addr = _address_only()
    perp = info.user_state(addr)
    spot = info.spot_user_state(addr)

    out = {
        "address": addr,
        "perp_account_value": float(perp["marginSummary"]["accountValue"]),
        "perp_withdrawable": float(perp["withdrawable"]),
        "open_positions": len(perp.get("assetPositions", [])),
        "spot_balances": spot.get("balances", []),
    }
    print(json.dumps(out, indent=2))


def _get_mid(info: Info, symbol: str) -> float:
    mids = info.all_mids()
    if symbol not in mids:
        raise RuntimeError(f"symbol not in mids: {symbol}")
    return float(mids[symbol])


def _risk_checks(info: Info, address: str, notional: float, cfg: RiskConfig) -> Dict[str, Any]:
    if KILL_SWITCH.exists():
        raise RuntimeError(f"Kill switch active: {KILL_SWITCH}")
    if notional > cfg.max_notional_usd:
        raise RuntimeError(f"notional {notional} > max {cfg.max_notional_usd}")

    st = _load_risk_state()
    today = time.strftime("%Y-%m-%d")
    if st.get("day") != today:
        st = {"day": today, "start_value": None, "daily_realized_pnl": 0.0, "last_order_ts": None}

    us = info.user_state(address)
    acct_val = float(us["marginSummary"]["accountValue"])
    if st["start_value"] is None:
        st["start_value"] = acct_val

    daily_loss_pct = 0.0
    if st["start_value"] and st["start_value"] > 0:
        daily_loss_pct = max(0.0, (st["start_value"] - acct_val) / st["start_value"] * 100.0)
    if daily_loss_pct >= cfg.max_daily_loss_pct:
        raise RuntimeError(f"daily loss limit hit: {daily_loss_pct:.2f}% >= {cfg.max_daily_loss_pct}%")

    open_pos = len(us.get("assetPositions", []))
    if open_pos >= cfg.max_open_positions:
        raise RuntimeError(f"open positions {open_pos} >= max {cfg.max_open_positions}")

    _save_risk_state(st)
    return {"account_value": acct_val, "daily_loss_pct": daily_loss_pct, "open_positions": open_pos}


def place_market(symbol: str, side: str, usd_size: float, leverage: int, execute: bool) -> None:
    side = side.lower().strip()
    if side not in {"buy", "sell"}:
        raise RuntimeError("side must be buy|sell")

    info, exch, addr, cfg = _setup()
    risk = _risk_checks(info, addr, usd_size, cfg)

    mid = _get_mid(info, symbol)
    sz = usd_size / mid
    is_buy = side == "buy"

    plan = {
        "symbol": symbol,
        "side": side,
        "usd_size": usd_size,
        "mid": mid,
        "size": sz,
        "slippage": cfg.max_slippage,
        "leverage": leverage,
        "execute": execute,
        "risk": risk,
        "ts": int(time.time()),
    }

    if not execute:
        print(json.dumps({"mode": "DRY_RUN", "plan": plan}, indent=2))
        return

    lev_res = exch.update_leverage(leverage, symbol, is_cross=True)
    ord_res = exch.market_open(symbol, is_buy=is_buy, sz=sz, slippage=cfg.max_slippage)

    event = {
        "type": "market_open",
        "plan": plan,
        "leverage_result": lev_res,
        "order_result": ord_res,
        "ts": int(time.time()),
    }
    _log(event)
    st = _load_risk_state()
    st["last_order_ts"] = int(time.time())
    _save_risk_state(st)

    print(json.dumps(event, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Hyperliquid execution engine (with risk guard)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show perp/spot status")

    p_order = sub.add_parser("order", help="place one market order")
    p_order.add_argument("--symbol", default="BTC", help="e.g. BTC, ETH")
    p_order.add_argument("--side", required=True, choices=["buy", "sell"])
    p_order.add_argument("--usd", type=float, required=True)
    p_order.add_argument("--leverage", type=int, default=2)
    p_order.add_argument("--execute", action="store_true", help="actually execute (default dry-run)")

    args = ap.parse_args()

    if args.cmd == "status":
        show_status()
    elif args.cmd == "order":
        place_market(args.symbol, args.side, args.usd, args.leverage, args.execute)


if __name__ == "__main__":
    main()
