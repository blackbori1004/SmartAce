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

WHALES = [w.strip() for w in os.getenv("HL_COPY_WHALES", "").split(",") if w.strip()]
INTERVAL = float(os.getenv("HL_COPY_INTERVAL_SEC", "2.5"))
LOOKBACK_SEC = int(os.getenv("HL_COPY_LOOKBACK_SEC", "20"))
SCALE = float(os.getenv("HL_COPY_SCALE", "0.0015"))
MAX_USD = float(os.getenv("HL_MAX_NOTIONAL_USD", "500"))
MIN_USD = float(os.getenv("HL_COPY_MIN_USD", "10"))
DEFAULT_LEV = int(os.getenv("HL_COPY_DEFAULT_LEVERAGE", "3"))
DRY_RUN = os.getenv("HL_COPY_DRY_RUN", "0") == "1"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    now_ms = int(time.time() * 1000)
    return {"last_ts": now_ms - LOOKBACK_SEC * 1000, "seen": {}}


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


def main():
    if not WHALES:
        raise RuntimeError("Set HL_COPY_WHALES env with comma-separated whale addresses")

    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    st = load_state()
    log(f"copytrader started whales={len(WHALES)} scale={SCALE} max_usd={MAX_USD} min_usd={MIN_USD} dry={DRY_RUN}")

    while True:
        try:
            end_ms = int(time.time() * 1000)
            start_ms = int(st.get("last_ts", end_ms - LOOKBACK_SEC * 1000))
            max_seen = start_ms

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
                        cmd = [
                            "python",
                            "scripts/hyperliquid_bot.py",
                            "close",
                            "--symbol",
                            coin,
                            "--retries",
                            "3",
                            "--wait",
                            "0.8",
                        ]
                        if DRY_RUN:
                            log(f"DRY close {coin} from whale={whale} dir={direction}")
                        else:
                            ok, out = run_cmd(cmd)
                            log(f"close {coin} whale={whale} ok={ok} out={out[:300]}")
                        continue

                    whale_notional = px * sz
                    usd = max(MIN_USD, whale_notional * SCALE)
                    usd = min(usd, MAX_USD)
                    lev = whale_leverage(info, whale, coin)

                    cmd = [
                        "python",
                        "scripts/hyperliquid_bot.py",
                        "order",
                        "--symbol",
                        coin,
                        "--side",
                        side,
                        "--usd",
                        f"{usd:.4f}",
                        "--leverage",
                        str(lev),
                    ]
                    if not DRY_RUN:
                        cmd.append("--execute")

                    ok, out = run_cmd(cmd)
                    log(
                        f"copy {coin} {side} usd={usd:.2f} lev={lev} whale={whale} dir={direction or '-'} ok={ok} out={out[:300]}"
                    )

            st["last_ts"] = max(max_seen, end_ms - 1000)
            # compact seen set
            cutoff = end_ms - 2 * 24 * 3600 * 1000
            st["seen"] = {k: v for k, v in st["seen"].items() if int(v) >= cutoff}
            save_state(st)
        except Exception as e:
            log(f"loop-error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
