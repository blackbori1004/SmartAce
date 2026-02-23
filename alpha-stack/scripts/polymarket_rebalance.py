#!/usr/bin/env python3
import json
import math
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
LOG_PATH = STATE_DIR / "polymarket_copy_log.jsonl"
ACTIVE_PATH = STATE_DIR / "polymarket_whales_active.json"
WEIGHTS_PATH = STATE_DIR / "polymarket_whale_weights.json"
REBAL_LOG = STATE_DIR / "polymarket_rebalance.log"

DEFAULT_WHALES = [
    "0x1979ae6b7e6534de9c4539d0c205e582ca637c9d",
    "0x1d0034134e339a309700ff2d34e99fa2d48b0313",
    "0x37c94ea1b44e01b18a1ce3ab6f8002bd6b9d7e6d",
]


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with REBAL_LOG.open("a") as f:
        f.write(line + "\n")


def load_active():
    if ACTIVE_PATH.exists():
        try:
            d = json.loads(ACTIVE_PATH.read_text())
            ws = d.get("whales") or []
            if ws:
                return [w.lower() for w in ws]
        except Exception:
            pass
    return DEFAULT_WHALES[:]


def save_active(whales, reason=""):
    ACTIVE_PATH.write_text(
        json.dumps({"whales": whales, "updatedAt": int(time.time()), "reason": reason}, indent=2)
    )


def load_recent_exec(lookback_h=24):
    if not LOG_PATH.exists():
        return []
    now = int(time.time())
    out = []
    for ln in LOG_PATH.read_text(errors="ignore").splitlines():
        try:
            x = json.loads(ln)
        except Exception:
            continue
        if x.get("mode") != "EXECUTE":
            continue
        ts = int(x.get("ts") or 0)
        if ts < now - lookback_h * 3600:
            continue
        out.append(x)
    return out


def fetch_candidate_wallets(limit=30):
    headers = {"User-Agent": "Mozilla/5.0"}
    agg = {}
    for off in range(0, 2000, 200):
        q = urllib.parse.urlencode({"limit": 200, "offset": off})
        req = urllib.request.Request(f"https://data-api.polymarket.com/trades?{q}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            arr = json.load(r)
        if not arr:
            break
        for t in arr:
            w = (t.get("proxyWallet") or "").lower()
            if not w:
                continue
            usd = float(t.get("size") or 0) * float(t.get("price") or 0)
            slug = t.get("slug") or ""
            a = agg.setdefault(w, {"usd": 0.0, "n": 0, "m": set()})
            a["usd"] += usd
            a["n"] += 1
            if slug:
                a["m"].add(slug)

    rows = []
    for w, a in agg.items():
        if a["n"] < 5:
            continue
        score = (math.log1p(a["usd"]) * 0.6) + (math.log1p(a["n"]) * 0.3) + (math.log1p(len(a["m"])) * 0.1)
        rows.append((score, w))
    rows.sort(reverse=True)
    return [w for _, w in rows[:limit]]


def build_hourly_weights(current_whales):
    rows = load_recent_exec(1)
    # weight from 1h quality avg: (consensus_weight * prob_weight)
    qmap = {w: [] for w in current_whales}
    for x in rows:
        w = (x.get("whale") or "").lower()
        if w not in qmap:
            continue
        q = float(x.get("consensus_weight") or 0) * float(x.get("prob_weight") or 0)
        if q > 0:
            qmap[w].append(q)

    raw = {}
    for w in current_whales:
        vals = qmap.get(w) or []
        avg = (sum(vals) / len(vals)) if vals else 1.0
        # clamp and normalize around 1.0
        raw[w] = min(1.6, max(0.7, avg))

    mean = sum(raw.values()) / len(raw) if raw else 1.0
    weights = {w: round(min(1.8, max(0.6, v / mean)), 3) for w, v in raw.items()} if mean > 0 else {w: 1.0 for w in raw}

    WEIGHTS_PATH.write_text(
        json.dumps({"updatedAt": int(time.time()), "weights": weights, "source": "1h_quality_avg"}, indent=2)
    )
    return weights


def score_current_whales(current_whales):
    rows = load_recent_exec(24)
    # fallback score from copied activity if no PnL fields available
    stat = {w: {"n": 0, "usd": 0.0, "wins": 0, "loss": 0} for w in current_whales}
    for x in rows:
        w = (x.get("whale") or "").lower()
        if w not in stat:
            continue
        stat[w]["n"] += 1
        stat[w]["usd"] += float(x.get("my_usd") or 0)
        # very rough proxy: consensus/prob weight above 1 treated as favorable signal quality
        q = float(x.get("consensus_weight") or 0) * float(x.get("prob_weight") or 0)
        if q >= 1:
            stat[w]["wins"] += 1
        else:
            stat[w]["loss"] += 1

    scored = []
    for w, s in stat.items():
        n = s["wins"] + s["loss"]
        win = (s["wins"] / n) if n else 0.5
        vol = min(1.0, math.log1p(s["usd"]) / 3.0)
        score = win * 0.7 + vol * 0.3
        scored.append({"wallet": w, "score": score, "samples": s["n"], "winProxy": win, "usd": s["usd"]})
    scored.sort(key=lambda x: x["score"])
    return scored


def restart_copytrader(whales):
    whales_csv = ",".join(whales)
    cmd = f'''cd {ROOT} && pkill -f "scripts/polymarket_copytrader.py" || true && nohup bash -lc 'source .venv/bin/activate && python -u scripts/polymarket_copytrader.py --whales "{whales_csv}" --loop --interval 5 --execute --usd-scale 0.08 --usd-cap 8 --min-whale-cash 50 --max-actions 3 --max-total-usd 12 --max-age-minutes 20 --tp-pct 9 --sl-pct 6 --max-hold-minutes 120' > state/polymarket_copytrader.log 2>&1 & echo $!'''
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip())
    return p.stdout.strip()


def main():
    current = load_active()
    scored = score_current_whales(current)
    candidates = fetch_candidate_wallets(30)

    low = scored[0] if scored else None
    replacement = next((w for w in candidates if w not in current), None)

    # refresh hourly dynamic whale weights (used by copytrader sizing)
    weights = build_hourly_weights(current)

    changed = False
    reason = "no_change"
    if low and replacement:
        # replace only when clearly weak to reduce churn
        if low["samples"] >= 8 and low["winProxy"] < 0.40:
            current = [replacement if w == low["wallet"] else w for w in current]
            changed = True
            reason = f"replaced {low['wallet']} -> {replacement} (winProxy={low['winProxy']:.2f}, samples={low['samples']})"

    if changed:
        pid = restart_copytrader(current)
        save_active(current, reason)
        weights = build_hourly_weights(current)
        log(f"REBALANCED: {reason}; pid={pid}; whales={current}; weights={weights}")
    else:
        save_active(current, reason)
        log(f"KEEP: whales={current}; low={low}; weights={weights}")


if __name__ == "__main__":
    main()
