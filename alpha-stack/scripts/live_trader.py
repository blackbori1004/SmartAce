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
INTERVAL = int(os.getenv("PAPER_INTERVAL_SEC", "3"))
MIN_SPREAD = float(os.getenv("PAPER_MIN_SPREAD_PCT", "0.20"))
USD_SIZE = float(os.getenv("PAPER_NOTIONAL_USD", "400"))
LEVERAGE = int(os.getenv("HL_LIVE_LEVERAGE", "5"))
SYMBOL = os.getenv("HL_LIVE_SYMBOL", "BTC")
ACCOUNT = os.getenv("HL_ACCOUNT_ADDRESS", "").strip()
MAX_LOSS_STREAK = int(os.getenv("HL_MAX_LOSS_STREAK", "3"))
BREAKEVEN_TRIGGER_PCT = float(os.getenv("HL_BREAKEVEN_TRIGGER_PCT", "0.20"))
SCALP_MODE = os.getenv("HL_SCALP_MODE", "1") == "1"
SCALP_RSI_LONG_BASE = float(os.getenv("HL_SCALP_RSI_LONG", "53"))
SCALP_RSI_SHORT_BASE = float(os.getenv("HL_SCALP_RSI_SHORT", "47"))
SCALP_ATR_MIN = float(os.getenv("HL_SCALP_ATR_MIN", "0.10"))
SCALP_ATR_MAX = float(os.getenv("HL_SCALP_ATR_MAX", "1.10"))
SCALP_BREAKOUT_BPS = float(os.getenv("HL_SCALP_BREAKOUT_BPS", "3.0"))
SCALP_FEE_BPS_RT = float(os.getenv("HL_SCALP_FEE_BPS_RT", "9.0"))
SCALP_SAFETY_BPS = float(os.getenv("HL_SCALP_SAFETY_BPS", "4.0"))

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
POS_PATH = STATE_DIR / "open_position.json"
TRADES_PATH = STATE_DIR / "trades.jsonl"
KILL_SWITCH = Path.home() / ".openclaw" / "workspace" / ".pi" / "hyperliquid.pause"
ADAPT_PATH = STATE_DIR / "scalp_params.json"

ALLOWED_CHAINS = {"ethereum", "base", "arbitrum", "optimism", "polygon", "bsc", "scroll", "linea", "manta", "soneium", "seiv2", "katana"}

adaptive = {
    "rsi_long": SCALP_RSI_LONG_BASE,
    "rsi_short": SCALP_RSI_SHORT_BASE,
    "min_spread": MIN_SPREAD,
    "updated_ts": 0,
}


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
    # 스캘핑 모드: 15m 추세 + 1m 모멘텀/돌파로 빈도 증가
    c15, _, _ = get_klines(symbol, "15m", 180)
    c1m, h1m, l1m = get_klines(symbol, "1m", 180)

    ema_fast = ema(c15[-120:], 20)
    ema_slow = ema(c15[-120:], 60)
    if ema_fast is None or ema_slow is None:
        return None, "ema-insufficient"

    trend = "buy" if ema_fast > ema_slow else "sell"

    r = rsi(c1m, 14)
    a = atr(h1m, l1m, c1m, 14)
    if r is None or a is None:
        return None, "indicator-insufficient"

    price = c1m[-1]
    atr_pct = (a / price) * 100 if price else 0
    hi = max(h1m[-15:-1])
    lo = min(l1m[-15:-1])
    breakout_pad = price * (SCALP_BREAKOUT_BPS / 10000.0)

    if atr_pct < SCALP_ATR_MIN or atr_pct > SCALP_ATR_MAX:
        return None, f"atr-filter {atr_pct:.3f}%"

    if trend == "buy":
        cond = r >= adaptive["rsi_long"] and price >= (hi - breakout_pad)
        return ("buy", f"scalp-up rsi={r:.1f} px={price:.1f} hi={hi:.1f}") if cond else (None, f"long-filter rsi={r:.1f}")
    else:
        cond = r <= adaptive["rsi_short"] and price <= (lo + breakout_pad)
        return ("sell", f"scalp-down rsi={r:.1f} px={price:.1f} lo={lo:.1f}") if cond else (None, f"short-filter rsi={r:.1f}")


def spread_ok(min_spread: float) -> tuple[bool, float]:
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
    return spread >= min_spread, spread


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


def load_adaptive():
    if ADAPT_PATH.exists():
        try:
            d = json.loads(ADAPT_PATH.read_text())
            adaptive["rsi_long"] = float(d.get("rsi_long", adaptive["rsi_long"]))
            adaptive["rsi_short"] = float(d.get("rsi_short", adaptive["rsi_short"]))
            adaptive["min_spread"] = float(d.get("min_spread", adaptive["min_spread"]))
            adaptive["updated_ts"] = int(d.get("updated_ts", 0))
        except Exception:
            pass


def save_adaptive():
    ADAPT_PATH.write_text(json.dumps(adaptive, ensure_ascii=False, indent=2))


def apply_adaptive_tuning():
    now = int(time.time())
    if adaptive.get("updated_ts", 0) and now - adaptive["updated_ts"] < 60:
        return

    if not TRADES_PATH.exists():
        return
    rows = []
    for ln in TRADES_PATH.read_text().strip().splitlines()[-60:]:
        try:
            t = json.loads(ln)
            if t.get("kind") == "closed":
                rows.append(t)
        except Exception:
            pass
    if len(rows) < 8:
        adaptive["updated_ts"] = now
        return

    wins = [x for x in rows if float(x.get("pnl_usd", 0)) > 0]
    wr = len(wins) / len(rows) * 100.0

    if wr < 45:
        adaptive["rsi_long"] = min(58.0, adaptive["rsi_long"] + 0.5)
        adaptive["rsi_short"] = max(42.0, adaptive["rsi_short"] - 0.5)
        adaptive["min_spread"] = min(0.35, adaptive["min_spread"] + 0.01)
    elif wr > 58:
        adaptive["rsi_long"] = max(51.5, adaptive["rsi_long"] - 0.3)
        adaptive["rsi_short"] = min(48.5, adaptive["rsi_short"] + 0.3)
        adaptive["min_spread"] = max(0.12, adaptive["min_spread"] - 0.005)

    adaptive["updated_ts"] = now
    save_adaptive()


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
    apply_adaptive_tuning()

    if KILL_SWITCH.exists():
        print("kill-switch active -> entry paused")
        return

    if has_open_position(SYMBOL):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] position-open -> skip entry")
        return

    max_slip_bps = float(os.getenv("HL_MAX_SLIPPAGE", "0.0012")) * 10000.0
    required_spread = max(adaptive["min_spread"], (SCALP_FEE_BPS_RT + SCALP_SAFETY_BPS + max_slip_bps) / 100.0)
    spread_pass, spread = spread_ok(required_spread)
    side, why = strategy_signal(SYMBOL)

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if not spread_pass or not side:
        print(f"[{ts}] no-entry spread={spread:.3f}% req={required_spread:.3f}% side={side} reason={why}")
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
    load_adaptive()
    print(
        f"live trader started: mode={'SCALP' if SCALP_MODE else 'TREND'}, pair={PAIR}, min_spread={adaptive['min_spread']}%, usd={USD_SIZE}, symbol={SYMBOL}, lev={LEVERAGE}x, every={INTERVAL}s"
    )
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"loop-error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
