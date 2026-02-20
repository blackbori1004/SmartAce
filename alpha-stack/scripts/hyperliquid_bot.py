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
POS_PATH = STATE_DIR / "open_position.json"
KILL_SWITCH = Path.home() / ".openclaw" / "workspace" / ".pi" / "hyperliquid.pause"


@dataclass
class RiskConfig:
    max_notional_usd: float = float(os.getenv("HL_MAX_NOTIONAL_USD", "400"))
    max_daily_loss_pct: float = float(os.getenv("HL_MAX_DAILY_LOSS_PCT", "3"))
    max_slippage: float = float(os.getenv("HL_MAX_SLIPPAGE", "0.003"))
    max_open_positions: int = int(os.getenv("HL_MAX_OPEN_POSITIONS", "1"))
    tp_pct: float = float(os.getenv("HL_TP_PCT", "3.0"))
    sl_pct: float = float(os.getenv("HL_SL_PCT", "2.0"))


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
    exch = Exchange(wallet, constants.MAINNET_API_URL, account_address=addr)
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


def _compute_tpsl(is_buy: bool, avg_px: float, cfg: RiskConfig) -> Dict[str, float]:
    # Long: TP above, SL below. Short: inverse.
    tp_px = avg_px * (1 + cfg.tp_pct / 100.0) if is_buy else avg_px * (1 - cfg.tp_pct / 100.0)
    sl_px = avg_px * (1 - cfg.sl_pct / 100.0) if is_buy else avg_px * (1 + cfg.sl_pct / 100.0)
    return {"tp_px": tp_px, "sl_px": sl_px}


def place_market(symbol: str, side: str, usd_size: float, leverage: int, execute: bool) -> None:
    side = side.lower().strip()
    if side not in {"buy", "sell"}:
        raise RuntimeError("side must be buy|sell")

    info, exch, addr, cfg = _setup()
    risk = _risk_checks(info, addr, usd_size, cfg)

    mid = _get_mid(info, symbol)
    raw_sz = usd_size / mid
    asset = info.name_to_asset(symbol)
    sz_decimals = info.asset_to_sz_decimals[asset]
    sz = float(f"{raw_sz:.{sz_decimals}f}")
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

    tpsl = None
    try:
        filled = ord_res.get("response", {}).get("data", {}).get("statuses", [{}])[0].get("filled")
        if filled:
            avg_px = float(filled["avgPx"])
            filled_sz = float(filled["totalSz"])
            tpsl = _compute_tpsl(is_buy, avg_px, cfg)
            POS_PATH.write_text(
                json.dumps(
                    {
                        "symbol": symbol,
                        "side": side,
                        "size": filled_sz,
                        "entry_px": avg_px,
                        "tp_px": tpsl["tp_px"],
                        "sl_px": tpsl["sl_px"],
                        "opened_ts": int(time.time()),
                    },
                    indent=2,
                )
            )
    except Exception as e:
        tpsl = {"error": str(e)}

    event = {
        "type": "market_open",
        "plan": plan,
        "leverage_result": lev_res,
        "order_result": ord_res,
        "tpsl": tpsl,
        "ts": int(time.time()),
    }
    _log(event)
    st = _load_risk_state()
    st["last_order_ts"] = int(time.time())
    _save_risk_state(st)

    print(json.dumps(event, indent=2))


def _position_size(info: Info, address: str, symbol: str) -> float:
    us = info.user_state(address)
    for p in us.get("assetPositions", []):
        pos = p.get("position", {})
        if pos.get("coin") == symbol:
            return abs(float(pos.get("szi", 0) or 0))
    return 0.0


def close_symbol(symbol: str, retries: int = 3, wait_sec: float = 0.8) -> None:
    info, exch, addr, _ = _setup()

    attempts = []
    final_size = _position_size(info, addr, symbol)
    for i in range(1, retries + 1):
        res = exch.market_close(symbol)
        attempts.append({"attempt": i, "result": res, "ts": int(time.time())})
        time.sleep(wait_sec)
        final_size = _position_size(info, addr, symbol)
        if final_size <= 0:
            break

    event = {
        "type": "market_close",
        "symbol": symbol,
        "address": addr,
        "attempts": attempts,
        "final_open_size": final_size,
        "forced_flat": final_size <= 0,
        "ts": int(time.time()),
    }
    _log(event)

    # 로컬 포지션 파일은 실제 평탄화 확인 후에만 삭제
    if final_size <= 0 and POS_PATH.exists():
        try:
            d = json.loads(POS_PATH.read_text())
            if d.get("symbol") == symbol:
                POS_PATH.unlink(missing_ok=True)
        except Exception:
            pass

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

    p_close = sub.add_parser("close", help="close symbol market")
    p_close.add_argument("--symbol", required=True)
    p_close.add_argument("--retries", type=int, default=3)
    p_close.add_argument("--wait", type=float, default=0.8, help="wait seconds between retries")

    args = ap.parse_args()

    if args.cmd == "status":
        show_status()
    elif args.cmd == "order":
        place_market(args.symbol, args.side, args.usd, args.leverage, args.execute)
    elif args.cmd == "close":
        close_symbol(args.symbol, retries=args.retries, wait_sec=args.wait)


if __name__ == "__main__":
    main()
