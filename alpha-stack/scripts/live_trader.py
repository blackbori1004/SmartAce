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
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
PAIR = os.getenv("DEX_PAIR", "WETH/USDC")
INTERVAL = int(os.getenv("PAPER_INTERVAL_SEC", "8"))
MIN_SPREAD = float(os.getenv("PAPER_MIN_SPREAD_PCT", "0.35"))
USD_SIZE = float(os.getenv("PAPER_NOTIONAL_USD", "100"))
LEVERAGE = int(os.getenv("HL_LIVE_LEVERAGE", "5"))  # 공격적 상향 기본 5x
SYMBOL = os.getenv("HL_LIVE_SYMBOL", "BTC")
ACCOUNT = os.getenv("HL_ACCOUNT_ADDRESS", "").strip()
MAX_LOSS_STREAK = int(os.getenv("HL_MAX_LOSS_STREAK", "3"))
BREAKEVEN_TRIGGER_PCT = float(os.getenv("HL_BREAKEVEN_TRIGGER_PCT", "0.6"))

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
POS_PATH = STATE_DIR / "open_position.json"
TRADES_PATH = STATE_DIR / "trades.jsonl"
KILL_SWITCH = Path.home() / ".openclaw" / "workspace" / ".pi" / "hyperliquid.pause"

ALLOWED_CHAINS = {"ethereum", "base", "arbitrum", "optimism", "polygon", "bsc", "scroll", "linea", "manta", "soneium", "seiv2", "katana"}


def ema(vals, n):
    if len(vals) < n:
        return None
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(vals, n=14):
    if len(vals) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-n:]) / n
    al = sum(losses[-n:]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - (100 / (1 + rs))


def atr(highs, lows, closes, n=14):
    if len(closes) < n + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-n:]) / n


def get_klines(symbol: str, interval: str, limit: int):
    p = {"symbol": f"{symbol}USDT", "interval": interval, "limit": limit}
    r = requests.get(BINANCE_KLINES, params=p, timeout=10)
    r.raise_for_status()
    k = r.json()
    closes = [float(x[4]) for x in k]
    highs = [float(x[2]) for x in k]
    lows = [float(x[3]) for x in k]
    return closes, highs, lows


def strategy_signal(symbol: str):
    # 전문가 컨플루언스: HTF 추세 + LTF 모멘텀 + 변동성 + 돌파
    c1h, _, _ = get_klines(symbol, "1h", 260)
    c5m, h5m, l5m = get_klines(symbol, "5m", 220)

    ema50 = ema(c1h[-200:], 50)
    ema200 = ema(c1h[-200:], 200)
    if ema50 is None or ema200 is None:
        return None, "ema-insufficient"

    trend = "buy" if ema50 > ema200 else "sell"

    r = rsi(c5m, 14)
    a = atr(h5m, l5m, c5m, 14)
    if r is None or a is None:
        return None, "indicator-insufficient"

    price = c5m[-1]
    atr_pct = (a / price) * 100 if price else 0
    hi20 = max(h5m[-21:-1])
    lo20 = min(l5m[-21:-1])

    # 변동성 밴드: 너무 조용/너무 과열 구간 제외
    if atr_pct < 0.12 or atr_pct > 1.8:
        return None, f"atr-filter {atr_pct:.3f}%"

    if trend == "buy":
        cond = r >= 55 and price > hi20
        return ("buy", f"trend=up rsi={r:.1f} breakout={price:.1f}>{hi20:.1f}") if cond else (None, f"long-filter rsi={r:.1f}")
    else:
        cond = r <= 45 and price < lo20
        return ("sell", f"trend=down rsi={r:.1f} breakdown={price:.1f}<{lo20:.1f}") if cond else (None, f"short-filter rsi={r:.1f}")


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


def loss_streak() -> int:
    if not TRADES_PATH.exists():
        return 0
    streak = 0
    for ln in TRADES_PATH.read_text().strip().splitlines()[::-1]:
        try:
            t = json.loads(ln)
            if t.get("kind") != "closed":
                continue
            if t.get("pnl_usd", 0) < 0:
                streak += 1
            else:
                break
        except Exception:
            pass
    return streak


def log_trade(obj: dict):
    with TRADES_PATH.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


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
        hit, reason = False, None

        # 수익이 일정 구간 이상 나면 손절을 본절로 올려 이익 잠금
        entry = float(pos["entry_px"])
        if side == "buy":
            be_trigger = entry * (1 + BREAKEVEN_TRIGGER_PCT / 100.0)
            if mid >= be_trigger and sl < entry:
                pos["sl_px"] = entry
                POS_PATH.write_text(json.dumps(pos, indent=2))
                sl = entry
                print(f"[BE] long stop moved to breakeven @ {entry:.2f}")
        else:
            be_trigger = entry * (1 - BREAKEVEN_TRIGGER_PCT / 100.0)
            if mid <= be_trigger and sl > entry:
                pos["sl_px"] = entry
                POS_PATH.write_text(json.dumps(pos, indent=2))
                sl = entry
                print(f"[BE] short stop moved to breakeven @ {entry:.2f}")

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
            cmd = [
                "python",
                "scripts/hyperliquid_bot.py",
                "close",
                "--symbol",
                symbol,
                "--retries",
                "5",
                "--wait",
                "1.0",
            ]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode == 0:
                print(p.stdout.strip())
                try:
                    close_ev = json.loads(p.stdout)
                except Exception:
                    close_ev = {}
                if close_ev.get("forced_flat"):
                    pnl = (mid - float(pos["entry_px"])) * float(pos["size"]) * (1 if side == "buy" else -1)
                    log_trade({
                        "kind": "closed",
                        "symbol": symbol,
                        "side": side,
                        "entry": pos["entry_px"],
                        "exit": mid,
                        "size": pos["size"],
                        "reason": reason,
                        "pnl_usd": pnl,
                        "ts": int(time.time()),
                    })
                    if pnl < 0 and loss_streak() >= MAX_LOSS_STREAK:
                        KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
                        KILL_SWITCH.write_text(f"paused at {int(time.time())}: loss streak reached")
                        print(f"[PAUSE] loss streak >= {MAX_LOSS_STREAK}, kill switch ON")
                else:
                    print("[WARN] close attempted but position not fully flat yet")
            else:
                print((p.stderr or p.stdout).strip())
            return True
    except Exception as e:
        print(f"tpsl-check-error: {e}")
    return False


def run_once():
    maybe_close_on_tpsl()

    if KILL_SWITCH.exists():
        print("kill-switch active -> entry paused")
        return

    if has_open_position(SYMBOL):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] position-open -> skip entry")
        return

    spread_pass, spread = spread_ok()
    side, why = strategy_signal(SYMBOL)

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if not spread_pass or not side:
        print(f"[{ts}] no-entry spread={spread:.3f}% side={side} reason={why}")
        return

    print(f"[{ts}] SIGNAL side={side} spread={spread:.3f}% reason={why} -> try order")
    cmd = [
        "python",
        "scripts/hyperliquid_bot.py",
        "order",
        "--symbol",
        SYMBOL,
        "--side",
        side,
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
        try:
            d = json.loads(p.stdout)
            o = d.get("order_result", {}).get("response", {}).get("data", {}).get("statuses", [{}])[0].get("filled")
            if o:
                log_trade({
                    "kind": "opened",
                    "symbol": SYMBOL,
                    "side": side,
                    "entry": float(o["avgPx"]),
                    "size": float(o["totalSz"]),
                    "ts": int(time.time()),
                })
        except Exception:
            pass
    else:
        print(f"[{ts}] order-skip/error")
        print((p.stderr or p.stdout).strip())


def main():
    print(
        f"live trader started: pair={PAIR}, min_spread={MIN_SPREAD}%, usd={USD_SIZE}, symbol={SYMBOL}, lev={LEVERAGE}x, every={INTERVAL}s"
    )
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"loop-error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
