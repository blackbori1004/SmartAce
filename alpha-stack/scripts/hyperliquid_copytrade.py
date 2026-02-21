#!/usr/bin/env python3
import json
import os
import subprocess
import time
from pathlib import Path

from hyperliquid.info import Info
from hyperliquid.utils import constants

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)
STATE_PATH = STATE_DIR / "hyperliquid_copy_state.json"
LOG_PATH = STATE_DIR / "hyperliquid_copy.log"

WHALES = [w.strip().lower() for w in os.getenv("HL_COPY_WHALES", "").split(",") if w.strip()]
INTERVAL = float(os.getenv("HL_COPY_INTERVAL_SEC", "2.5"))
LOOKBACK_SEC = int(os.getenv("HL_COPY_LOOKBACK_SEC", "20"))
SCALE = float(os.getenv("HL_COPY_SCALE", "0.0015"))
MAX_USD = float(os.getenv("HL_MAX_NOTIONAL_USD", "500"))
MIN_USD = float(os.getenv("HL_COPY_MIN_USD", "10"))
DEFAULT_LEV = int(os.getenv("HL_COPY_DEFAULT_LEVERAGE", "3"))
DUP_COOLDOWN_SEC = int(os.getenv("HL_COPY_DUPLICATE_COOLDOWN_SEC", "45"))
DRY_RUN = os.getenv("HL_COPY_DRY_RUN", "0") == "1"


def _parse_weights() -> dict:
    raw = os.getenv("HL_COPY_WHALE_WEIGHTS", "").strip()
    out = {}
    if not raw:
        return out
    # format: 0xabc:1.2,0xdef:0.8
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        try:
            out[k.strip().lower()] = max(0.1, float(v.strip()))
        except Exception:
            continue
    return out


WHALE_WEIGHTS = _parse_weights()


def whale_weight(addr: str) -> float:
    return float(WHALE_WEIGHTS.get(addr.lower(), 1.0))


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def load_state():
    if STATE_PATH.exists():
        st = json.loads(STATE_PATH.read_text())
        st.setdefault("last_ts", int(time.time() * 1000) - LOOKBACK_SEC * 1000)
        st.setdefault("seen", {})
        st.setdefault("recent_symbol_side", {})
        return st
    now_ms = int(time.time() * 1000)
    return {"last_ts": now_ms - LOOKBACK_SEC * 1000, "seen": {}, "recent_symbol_side": {}}


def save_state(st):
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def whale_leverage(info: Info, whale: str, coin: str) -> int:
    try:
        us = info.user_state(whale)
        for p in us.get("assetPositions", []):
            pos = p.get("position", {})
            if pos.get("coin") == coin:
                lev = int(float((pos.get("leverage") or {}).get("value", DEFAULT_LEV)))
                return max(1, min(lev, 20))
    except Exception:
        pass
    return DEFAULT_LEV


def run_cmd(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout).strip()
    return True, p.stdout.strip()


def _symbol_side_key(coin: str, side: str) -> str:
    return f"{coin.upper()}:{side.lower()}"


def main():
    if not WHALES:
        raise RuntimeError("Set HL_COPY_WHALES env with comma-separated whale addresses")

    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    st = load_state()
    log(
        f"copytrader started whales={len(WHALES)} scale={SCALE} max_usd={MAX_USD} min_usd={MIN_USD} dry={DRY_RUN} dupCooldown={DUP_COOLDOWN_SEC}s"
    )

    while True:
        try:
            end_ms = int(time.time() * 1000)
            start_ms = int(st.get("last_ts", end_ms - LOOKBACK_SEC * 1000))
            max_seen = start_ms

            open_candidates = {}  # one best per symbol+side for each loop
            close_candidates = {}  # one close per symbol for each loop

            for whale in WHALES:
                fills = info.user_fills_by_time(whale, start_ms, end_ms, aggregate_by_time=True)
                fills = sorted(fills, key=lambda x: int(x.get("time", 0)))

                for f in fills:
                    ts = int(f.get("time", 0))
                    if ts <= start_ms:
                        continue
                    max_seen = max(max_seen, ts)

                    tid = str(f.get("tid") or f.get("hash") or f.get("oid") or f"{whale}:{ts}")
                    key = f"{whale}:{tid}"
                    if st["seen"].get(key):
                        continue
                    st["seen"][key] = ts

                    coin = str(f.get("coin", ""))
                    if not coin or coin.startswith("@") or ":" in coin:
                        continue  # skip spot / non-standard

                    px = abs(float(f.get("px", 0) or 0))
                    sz = abs(float(f.get("sz", 0) or 0))
                    if px <= 0 or sz <= 0:
                        continue

                    side_raw = str(f.get("side", "")).upper()
                    side = "buy" if side_raw == "B" else "sell"
                    direction = str(f.get("dir", ""))

                    if "Close" in direction:
                        # One close per symbol in one loop is enough
                        close_candidates[coin.upper()] = {
                            "coin": coin.upper(),
                            "whale": whale,
                            "dir": direction,
                        }
                        continue

                    whale_notional = px * sz
                    w = whale_weight(whale)
                    usd = max(MIN_USD, whale_notional * SCALE * w)
                    usd = min(usd, MAX_USD)
                    lev = whale_leverage(info, whale, coin)
                    k = _symbol_side_key(coin, side)

                    cand = {
                        "coin": coin.upper(),
                        "side": side,
                        "usd": usd,
                        "lev": lev,
                        "whale": whale,
                        "dir": direction,
                        "score": whale_notional * w,
                    }
                    prev = open_candidates.get(k)
                    if not prev or cand["score"] > prev["score"]:
                        open_candidates[k] = cand

            # 1) apply closes first
            for _, c in close_candidates.items():
                cmd = [
                    "python",
                    "scripts/hyperliquid_bot.py",
                    "close",
                    "--symbol",
                    c["coin"],
                    "--retries",
                    "3",
                    "--wait",
                    "0.8",
                ]
                if DRY_RUN:
                    log(f"DRY close {c['coin']} from whale={c['whale']} dir={c['dir']}")
                else:
                    ok, out = run_cmd(cmd)
                    log(f"close {c['coin']} whale={c['whale']} ok={ok} out={out[:300]}")

            # 2) apply opens with duplicate symbol+side cooldown
            now_sec = int(time.time())
            for k, c in open_candidates.items():
                last = int(st.get("recent_symbol_side", {}).get(k, 0) or 0)
                if last and now_sec - last < DUP_COOLDOWN_SEC:
                    log(f"skip-dup {k} whale={c['whale']} cooldown_left={DUP_COOLDOWN_SEC-(now_sec-last)}s")
                    continue

                cmd = [
                    "python",
                    "scripts/hyperliquid_bot.py",
                    "order",
                    "--symbol",
                    c["coin"],
                    "--side",
                    c["side"],
                    "--usd",
                    f"{c['usd']:.4f}",
                    "--leverage",
                    str(c["lev"]),
                ]
                if not DRY_RUN:
                    cmd.append("--execute")

                ok, out = run_cmd(cmd)
                if ok:
                    st.setdefault("recent_symbol_side", {})[k] = now_sec
                log(
                    f"copy {c['coin']} {c['side']} usd={c['usd']:.2f} lev={c['lev']} weight={whale_weight(c['whale']):.2f} whale={c['whale']} dir={c['dir'] or '-'} ok={ok} out={out[:300]}"
                )

            st["last_ts"] = max(max_seen, end_ms - 1000)
            cutoff = end_ms - 2 * 24 * 3600 * 1000
            st["seen"] = {k: v for k, v in st["seen"].items() if int(v) >= cutoff}
            cut_s = int(time.time()) - 6 * 3600
            st["recent_symbol_side"] = {k: v for k, v in st.get("recent_symbol_side", {}).items() if int(v) >= cut_s}
            save_state(st)
        except Exception as e:
            log(f"loop-error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
