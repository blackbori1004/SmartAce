#!/usr/bin/env python3
import json
import os
import subprocess
import time
from pathlib import Path

import requests
from hyperliquid.info import Info
from hyperliquid.utils import constants

DEX_URL = "https://api.dexscreener.com/latest/dex/search"
PAIR = os.getenv("DEX_PAIR", "WETH/USDC")
INTERVAL = int(os.getenv("PAPER_INTERVAL_SEC", "8"))
MIN_SPREAD = float(os.getenv("PAPER_MIN_SPREAD_PCT", "0.35"))
USD_SIZE = float(os.getenv("PAPER_NOTIONAL_USD", "100"))
LEVERAGE = int(os.getenv("HL_LIVE_LEVERAGE", "2"))
SYMBOL = os.getenv("HL_LIVE_SYMBOL", "BTC")
SIDE = os.getenv("HL_LIVE_SIDE", "buy")
ACCOUNT = os.getenv("HL_ACCOUNT_ADDRESS", "").strip()

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
POS_PATH = STATE_DIR / "open_position.json"

ALLOWED_CHAINS = {"ethereum", "base", "arbitrum", "optimism", "polygon", "bsc", "scroll", "linea", "manta", "soneium", "seiv2", "katana"}


def spread_ok() -> tuple[bool, float]:
    want_base, want_quote = [x.strip().upper() for x in PAIR.split("/")]
    base_alias = {want_base, "WETH"} if want_base == "ETH" else {want_base}
    quote_alias = {want_quote, "USDC.E", "USDB"} if want_quote == "USDC" else {want_quote}

    r = requests.get(DEX_URL, params={"q": PAIR}, timeout=10)
    r.raise_for_status()
    data = r.json()
    rows = []
    for p in data.get("pairs", []):
        price = float(p.get("priceUsd") or 0)
        liq = float((p.get("liquidity") or {}).get("usd") or 0)
        base = ((p.get("baseToken") or {}).get("symbol") or "").upper()
        quote = ((p.get("quoteToken") or {}).get("symbol") or "").upper()
        chain = p.get("chainId")
        if price > 0 and liq >= 100000 and chain in ALLOWED_CHAINS and base in base_alias and quote in quote_alias:
            rows.append(price)

    if len(rows) < 2:
        return False, 0.0
    low = min(rows)
    high = max(rows)
    spread = ((high - low) / low) * 100
    return spread >= MIN_SPREAD, spread


def has_open_position(symbol: str) -> bool:
    if not ACCOUNT:
        return False
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    us = info.user_state(ACCOUNT)
    for p in us.get("assetPositions", []):
        pos = p.get("position", {})
        if pos.get("coin") == symbol and abs(float(pos.get("szi", 0))) > 0:
            return True
    return False


def current_mid(symbol: str) -> float:
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    return float(info.all_mids().get(symbol, 0))


def maybe_close_on_tpsl() -> bool:
    if not POS_PATH.exists():
        return False
    try:
        pos = json.loads(POS_PATH.read_text())
        symbol = pos["symbol"]
        side = pos["side"].lower()
        tp = float(pos["tp_px"])
        sl = float(pos["sl_px"])
        mid = current_mid(symbol)
        hit = False
        reason = None

        if side == "buy":
            if mid >= tp:
                hit, reason = True, "tp"
            elif mid <= sl:
                hit, reason = True, "sl"
        else:
            if mid <= tp:
                hit, reason = True, "tp"
            elif mid >= sl:
                hit, reason = True, "sl"

        if hit:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {reason.upper()} hit @ {mid:.2f} -> closing {symbol}")
            cmd = ["python", "scripts/hyperliquid_bot.py", "close", "--symbol", symbol]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode == 0:
                print(p.stdout.strip())
            else:
                print((p.stderr or p.stdout).strip())
            return True
    except Exception as e:
        print(f"tpsl-check-error: {e}")
    return False


def run_once():
    # 1) 먼저 TP/SL 체크
    maybe_close_on_tpsl()

    # 2) 이미 포지션 있으면 신규진입 안 함
    if has_open_position(SYMBOL):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] position-open -> skip entry")
        return

    # 3) 신호 있으면 신규진입
    ok, spread = spread_ok()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if not ok:
        print(f"[{ts}] no-signal spread={spread:.3f}% (< {MIN_SPREAD}%)")
        return

    print(f"[{ts}] SIGNAL spread={spread:.3f}% -> trying live order")
    cmd = [
        "python",
        "scripts/hyperliquid_bot.py",
        "order",
        "--symbol",
        SYMBOL,
        "--side",
        SIDE,
        "--usd",
        str(USD_SIZE),
        "--leverage",
        str(LEVERAGE),
        "--execute",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode == 0:
        print(f"[{ts}] order-ok")
        print(p.stdout.strip())
    else:
        print(f"[{ts}] order-skip/error")
        print((p.stderr or p.stdout).strip())


def main():
    print(f"live trader started: pair={PAIR}, min_spread={MIN_SPREAD}%, usd={USD_SIZE}, symbol={SYMBOL}, side={SIDE}, every={INTERVAL}s")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"loop-error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
