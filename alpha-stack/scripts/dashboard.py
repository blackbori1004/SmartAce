#!/usr/bin/env python3
import base64
import binascii
import json
import os
import secrets
import shutil
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request
from websocket import WebSocketApp

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
except Exception:
    ClobClient = None

app = Flask(__name__)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEX_URL = "https://api.dexscreener.com/latest/dex/search"
DEX_PAIR = os.getenv("DEX_PAIR", "WETH/USDC")
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8788"))
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN") or secrets.token_urlsafe(12)

PAPER_INTERVAL_SEC = int(os.getenv("PAPER_INTERVAL_SEC", "8"))
PAPER_START_USD = float(os.getenv("PAPER_START_USD", "1000"))
PAPER_NOTIONAL_USD = float(os.getenv("PAPER_NOTIONAL_USD", "400"))
PAPER_MIN_SPREAD_PCT = float(os.getenv("PAPER_MIN_SPREAD_PCT", "0.35"))
PAPER_CAPTURE_RATIO = float(os.getenv("PAPER_CAPTURE_RATIO", "0.30"))
PAPER_COST_BPS = float(os.getenv("PAPER_COST_BPS", "10"))
HIST_PATH = Path(__file__).resolve().parents[1] / "state" / "fills.jsonl"
TRADES_PATH = Path(__file__).resolve().parents[1] / "state" / "trades.jsonl"
POLY_COPY_LOG_PATH = Path(__file__).resolve().parents[1] / "state" / "polymarket_copy_log.jsonl"
POLY_COPY_STATE_PATH = Path(__file__).resolve().parents[1] / "state" / "polymarket_copy_state.json"
POLY_ENV_PATH = Path(__file__).resolve().parents[1] / ".env.polymarket"

state: Dict[str, Any] = {
    "ws_connected": False,
    "ws_last_type": None,
    "ws_last_ts": None,
    "ws_messages": 0,
    "ws_error": None,
}

paper: Dict[str, Any] = {
    "startUsd": PAPER_START_USD,
    "cashUsd": PAPER_START_USD,
    "pnlUsd": 0.0,
    "trades": 0,
    "wins": 0,
    "losses": 0,
    "lastSpreadPct": None,
    "lastUpdateTs": None,
    "lastTrade": None,
    "recent": [],
}


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def auth_ok() -> bool:
    token = request.args.get("token") or request.headers.get("X-Alpha-Token")
    return token == DASHBOARD_TOKEN


@app.before_request
def guard():
    if request.path in ["/", "/api/status"] and not auth_ok():
        abort(401)


def ws_on_open(ws):
    state["ws_connected"] = True
    state["ws_error"] = None
    ws.send(json.dumps({"type": "subscribe", "channel": "market"}))


def ws_on_message(_ws, message):
    state["ws_messages"] += 1
    state["ws_last_ts"] = int(time.time())
    try:
        data = json.loads(message)
        state["ws_last_type"] = data.get("type") or data.get("event") or "unknown"
    except Exception:
        state["ws_last_type"] = "raw"


def ws_on_error(_ws, error):
    state["ws_connected"] = False
    state["ws_error"] = str(error)


def ws_on_close(_ws, _code, _msg):
    state["ws_connected"] = False


def ws_worker():
    while True:
        try:
            ws = WebSocketApp(
                WS_URL,
                on_open=ws_on_open,
                on_message=ws_on_message,
                on_error=ws_on_error,
                on_close=ws_on_close,
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            state["ws_error"] = str(e)
            state["ws_connected"] = False
        time.sleep(2)


def rpc_block() -> Dict[str, Any]:
    url = os.getenv("ETH_RPC_URL")
    if not url:
        return {"ok": False, "error": "ETH_RPC_URL not set"}
    try:
        payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        data = r.json()
        h = data.get("result")
        if not h:
            return {"ok": False, "error": f"No result: {data}"}
        return {"ok": True, "block": int(h, 16), "hex": h}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dex_spread(pair: str = DEX_PAIR) -> Dict[str, Any]:
    allowed_chains = {
        "ethereum",
        "base",
        "arbitrum",
        "optimism",
        "polygon",
        "bsc",
        "scroll",
        "linea",
        "manta",
        "soneium",
        "seiv2",
        "katana",
    }
    want_base, want_quote = [x.strip().upper() for x in pair.split("/")]
    base_alias = {want_base, "WETH"} if want_base == "ETH" else {want_base}
    quote_alias = {want_quote, "USDC.E", "USDB"} if want_quote == "USDC" else {want_quote}
    try:
        r = requests.get(DEX_URL, params={"q": pair}, timeout=10)
        r.raise_for_status()
        data = r.json()
        rows = []
        for p in data.get("pairs", []):
            price = float(p.get("priceUsd") or 0)
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
            base = ((p.get("baseToken") or {}).get("symbol") or "").upper()
            quote = ((p.get("quoteToken") or {}).get("symbol") or "").upper()
            chain = p.get("chainId")
            if price > 0 and liq >= 100000 and chain in allowed_chains and base in base_alias and quote in quote_alias:
                rows.append(
                    {
                        "dex": p.get("dexId"),
                        "chain": chain,
                        "price": price,
                        "liq": liq,
                    }
                )
        if len(rows) < 2:
            return {"ok": False, "error": "Not enough liquid pairs"}
        rows.sort(key=lambda x: x["price"])
        low = rows[0]
        high = rows[-1]
        spread = ((high["price"] - low["price"]) / low["price"]) * 100
        return {"ok": True, "low": low, "high": high, "spreadPct": spread}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def hyperliquid_state() -> Dict[str, Any]:
    addr = os.getenv("HL_ACCOUNT_ADDRESS", "").strip()
    if not addr:
        return {"ok": False, "error": "HL_ACCOUNT_ADDRESS 미설정"}
    try:
        perp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "clearinghouseState", "user": addr},
            timeout=8,
        ).json()
        spot = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "spotClearinghouseState", "user": addr},
            timeout=8,
        ).json()
        spot_bal = spot.get("balances", [])
        usdc_total = 0.0
        for b in spot_bal:
            if b.get("coin") == "USDC":
                usdc_total = float(b.get("total", 0) or 0)

        pos_rows = []
        for ap in perp.get("assetPositions", []):
            p = ap.get("position", {})
            szi = float(p.get("szi", 0) or 0)
            pos_rows.append(
                {
                    "symbol": p.get("coin"),
                    "side": "LONG" if szi > 0 else "SHORT",
                    "size": abs(szi),
                    "leverage": float((p.get("leverage") or {}).get("value", 0) or 0),
                    "entryPx": float(p.get("entryPx", 0) or 0),
                    "positionValue": float(p.get("positionValue", 0) or 0),
                    "unrealizedPnl": float(p.get("unrealizedPnl", 0) or 0),
                }
            )

        perp_value = float(perp.get("marginSummary", {}).get("accountValue", 0) or 0)
        return {
            "ok": True,
            "address": addr,
            "perpValue": perp_value,
            "withdrawable": float(perp.get("withdrawable", 0) or 0),
            "openPositions": len(perp.get("assetPositions", [])),
            "positions": pos_rows,
            "spotBalances": spot_bal,
            "walletTotal": perp_value + usdc_total,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_history(limit: int = 15) -> list:
    if not HIST_PATH.exists():
        return []
    lines = HIST_PATH.read_text().strip().splitlines()
    out = []
    for ln in lines[-limit:][::-1]:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def load_trade_stats(limit: int = 30) -> Dict[str, Any]:
    rows = []
    if TRADES_PATH.exists():
        for ln in TRADES_PATH.read_text().strip().splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass

    # fallback: if no normalized trades yet, derive lightweight history from fills logs
    if not rows and HIST_PATH.exists():
        for ln in HIST_PATH.read_text().strip().splitlines():
            try:
                x = json.loads(ln)
            except Exception:
                continue
            t = x.get("type")
            if t == "market_open":
                f = (x.get("order_result") or {}).get("response", {}).get("data", {}).get("statuses", [{}])[0].get("filled")
                if f:
                    rows.append({
                        "kind": "opened",
                        "symbol": x.get("plan", {}).get("symbol"),
                        "side": x.get("plan", {}).get("side"),
                        "entry": float(f.get("avgPx", 0) or 0),
                        "size": float(f.get("totalSz", 0) or 0),
                        "ts": x.get("ts"),
                    })
            elif t == "market_close":
                f = (x.get("result") or {}).get("response", {}).get("data", {}).get("statuses", [{}])[0].get("filled")
                if f:
                    rows.append({
                        "kind": "closed",
                        "symbol": x.get("symbol"),
                        "side": "-",
                        "entry": None,
                        "exit": float(f.get("avgPx", 0) or 0),
                        "size": float(f.get("totalSz", 0) or 0),
                        "reason": "manual/market_close",
                        "pnl_usd": 0.0,
                        "ts": x.get("ts"),
                    })

    closed = [x for x in rows if x.get("kind") == "closed"]
    wins = [x for x in closed if float(x.get("pnl_usd", 0)) > 0]
    cum = sum(float(x.get("pnl_usd", 0)) for x in closed)
    wr = (len(wins) / len(closed) * 100.0) if closed else 0.0
    return {"trades": rows[-limit:][::-1], "closed": len(closed), "wins": len(wins), "winRate": wr, "cumPnl": cum}


def _looks_base64(s: str) -> bool:
    try:
        base64.b64decode(s, validate=True)
        return True
    except (binascii.Error, ValueError):
        return False


def _polymarket_client():
    if ClobClient is None or not POLY_ENV_PATH.exists():
        return None
    try:
        load_dotenv(POLY_ENV_PATH, override=False)
        host = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com").strip()
        chain_id = int(os.getenv("POLYMARKET_CHAIN_ID", "137").strip())
        pk = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()
        funder = os.getenv("POLYMARKET_FUNDER", "").strip()
        sig_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "2").strip())
        if not pk or not funder:
            return None

        c = ClobClient(host, key=pk, chain_id=chain_id, signature_type=sig_type, funder=funder)
        k = os.getenv("POLYMARKET_API_KEY", "").strip()
        s = os.getenv("POLYMARKET_API_SECRET", "").strip()
        p = os.getenv("POLYMARKET_API_PASSPHRASE", "").strip()
        if k and s and p and _looks_base64(s):
            c.set_api_creds(ApiCreds(api_key=k, api_secret=s, api_passphrase=p))
        else:
            c.set_api_creds(c.create_or_derive_api_creds())
        return c
    except Exception:
        return None


def load_polymarket_copy_stats(limit: int = 20) -> Dict[str, Any]:
    rows = []
    if POLY_COPY_LOG_PATH.exists():
        for ln in POLY_COPY_LOG_PATH.read_text().strip().splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass

    recent = rows[-limit:][::-1]
    executed = [x for x in rows if x.get("mode") == "EXECUTE"]
    dry = [x for x in rows if x.get("mode") == "DRY_RUN"]
    closed = [x for x in rows if x.get("mode") == "CLOSE"]
    total_exec_usd = sum(float(x.get("my_usd", 0) or 0) for x in executed)

    wins = 0
    cum_pnl_usd = 0.0
    for c in closed:
        entry = float(c.get("entry_price", 0) or 0)
        last = float(c.get("last_price", 0) or 0)
        qty = float(c.get("qty", 0) or 0)
        pnl = (last - entry) * qty
        if pnl > 0:
            wins += 1
        cum_pnl_usd += pnl

    wr = (wins / len(closed) * 100.0) if closed else 0.0

    positions = []
    # 1) 우선 state 파일의 실시간 포지션 사용
    if POLY_COPY_STATE_PATH.exists():
        try:
            st = json.loads(POLY_COPY_STATE_PATH.read_text())
            for asset, p in (st.get("positions") or {}).items():
                positions.append(
                    {
                        "asset": asset,
                        "title": p.get("title") or p.get("slug") or asset[:10],
                        "side": "LONG",
                        "qty": float(p.get("qty", 0) or 0),
                        "entry": float(p.get("entry_price", 0) or 0),
                        "leverage": 1,
                        "pnl": None,
                    }
                )
        except Exception:
            pass

    # 2) state가 비었으면 로그 기반으로 복원 (이전 버전 호환)
    if not positions:
        agg = {}
        for x in rows:
            m = x.get("mode")
            if m == "EXECUTE":
                res = x.get("result") or {}
                if str(res.get("status")) != "matched":
                    continue
                asset = str(x.get("asset") or "")
                qty = float(res.get("takingAmount") or 0)
                cost = float(res.get("makingAmount") or x.get("my_usd") or 0)
                if not asset or qty <= 0:
                    continue
                if asset not in agg:
                    agg[asset] = {
                        "asset": asset,
                        "title": x.get("title") or x.get("slug") or asset[:10],
                        "qty": 0.0,
                        "cost": 0.0,
                    }
                agg[asset]["qty"] += qty
                agg[asset]["cost"] += cost
            elif m == "CLOSE":
                asset = str(x.get("asset") or "")
                qty = float(x.get("qty") or 0)
                if asset in agg:
                    agg[asset]["qty"] = max(0.0, agg[asset]["qty"] - qty)

        for asset, a in agg.items():
            if a["qty"] <= 0:
                continue
            entry = a["cost"] / a["qty"] if a["qty"] > 0 else 0
            positions.append(
                {
                    "asset": asset,
                    "title": a["title"],
                    "side": "LONG",
                    "qty": a["qty"],
                    "entry": entry,
                    "leverage": 1,
                    "pnl": None,
                }
            )

    wallet_total = None
    c = _polymarket_client()
    if c is not None:
        try:
            sig_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "2"))
            bal = c.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=sig_type))
            collateral_usdc = float(bal.get("balance", 0) or 0) / 1_000_000.0

            # 포지션 평가금액/미실현 PnL 계산
            pos_value = 0.0
            for p in positions:
                qty = float(p.get("qty", 0) or 0)
                entry = float(p.get("entry", 0) or 0)
                if qty <= 0:
                    continue
                mark_px = 0.0
                try:
                    mark_px = float(c.get_last_trade_price(p["asset"]) or 0)
                except Exception:
                    mark_px = 0.0

                if mark_px > 0:
                    p["pnl"] = (mark_px - entry) * qty
                    pos_value += mark_px * qty
                else:
                    # 시세 조회 실패 시 entry 기준 보수 추정
                    p["pnl"] = 0.0
                    pos_value += entry * qty

            wallet_total = collateral_usdc + pos_value
        except Exception:
            wallet_total = None

    return {
        "total": len(rows),
        "executed": len(executed),
        "dryRuns": len(dry),
        "closed": len(closed),
        "wins": wins,
        "winRate": wr,
        "cumPnlUsd": cum_pnl_usd,
        "execUsd": total_exec_usd,
        "walletTotal": wallet_total,
        "positions": positions,
        "recent": recent,
    }


def paper_worker():
    while True:
        snap = dex_spread()
        now = int(time.time())
        paper["lastUpdateTs"] = now
        if snap.get("ok"):
            spread = float(snap["spreadPct"])
            paper["lastSpreadPct"] = spread
            if spread >= PAPER_MIN_SPREAD_PCT:
                edge = (spread / 100.0) * PAPER_CAPTURE_RATIO
                costs = PAPER_COST_BPS / 10000.0
                pnl = PAPER_NOTIONAL_USD * (edge - costs)

                paper["cashUsd"] += pnl
                paper["pnlUsd"] = paper["cashUsd"] - paper["startUsd"]
                paper["trades"] += 1
                if pnl >= 0:
                    paper["wins"] += 1
                else:
                    paper["losses"] += 1

                trade = {
                    "ts": now,
                    "spreadPct": round(spread, 4),
                    "notionalUsd": PAPER_NOTIONAL_USD,
                    "captureRatio": PAPER_CAPTURE_RATIO,
                    "costBps": PAPER_COST_BPS,
                    "pnlUsd": round(pnl, 4),
                }
                paper["lastTrade"] = trade
                paper["recent"].insert(0, trade)
                paper["recent"] = paper["recent"][:10]

        time.sleep(PAPER_INTERVAL_SEC)


@app.get("/")
def index():
    html = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>Alpha Dashboard Pro</title>
  <style>
    body{font-family:Inter,system-ui;background:#0b1020;color:#e7ebff;padding:20px}
    .top{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}
    .muted{color:#95a0d0;font-size:12px}
    .ok{color:#42d392}.bad{color:#ff6b6b}
    .card{background:#141a33;border:1px solid #2a3366;border-radius:12px;padding:14px;margin-bottom:12px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{border-bottom:1px solid #253060;padding:8px;text-align:left;vertical-align:top}
    th{color:#b7c2f7;font-weight:600;background:#111831;position:sticky;top:0}
    .mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  </style>
</head>
<body>
  <div class='top'>
    <div><h2 style='margin:0'>에이스 트레이딩 대시보드 (Pro)</h2><div class='muted'>거래소 UI 스타일 · 5초 자동갱신</div></div>
    <div class='muted' id='updatedAt'>-</div>
  </div>

  <div class='card'>
    <h3>채널별 요약</h3>
    <table>
      <thead><tr><th>채널</th><th>거래수 (승/패/승률)</th><th>누적 PnL</th><th>현재 포지션 수</th><th>지갑 총 잔고</th></tr></thead>
      <tbody id='channelRows'></tbody>
    </table>
  </div>

  <div class='card'>
    <h3>현재 포지션</h3>
    <table>
      <thead><tr><th>채널</th><th>포지션명/페어</th><th>롱/숏</th><th>볼륨</th><th>레버리지</th><th>PnL</th></tr></thead>
      <tbody id='posRows'></tbody>
    </table>
  </div>

  <div class='card'>
    <h3>운영 상태</h3>
    <div id='ops'></div>
  </div>

<script>
const token = new URLSearchParams(window.location.search).get('token') || '';
const fmtUsd = (n)=> n===null||n===undefined ? '-' : '$'+Number(n).toFixed(2);
const fmtPct = (n)=> n===null||n===undefined ? '-' : Number(n).toFixed(1)+'%';

async function tick(){
  const r=await fetch('/api/status?token='+encodeURIComponent(token));
  if(!r.ok){document.body.innerHTML='<h3>접근 거부</h3><p>토큰 확인 필요</p>';return;}
  const d=await r.json();
  document.getElementById('updatedAt').innerText = new Date((d.ts||0)*1000).toLocaleString();

  const hl = d.hl || {};
  const ts = d.tradeStats || {closed:0,wins:0,winRate:0,cumPnl:0};
  const pc = d.polymarketCopy || {executed:0,closed:0,wins:0,winRate:0,cumPnlUsd:0,positions:[],walletTotal:null};

  const ch = [];
  ch.push(`<tr><td>Hyperliquid</td><td>${ts.closed} (${ts.wins}/${Math.max(0,ts.closed-ts.wins)}/${fmtPct(ts.winRate)})</td><td class='${Number(ts.cumPnl)>=0?'ok':'bad'}'>${fmtUsd(ts.cumPnl)}</td><td>${hl.openPositions ?? '-'}</td><td>${fmtUsd(hl.walletTotal)}</td></tr>`);
  ch.push(`<tr><td>Polymarket</td><td>${pc.closed||0} (${pc.wins||0}/${Math.max(0,(pc.closed||0)-(pc.wins||0))}/${fmtPct(pc.winRate)})</td><td class='${Number(pc.cumPnlUsd)>=0?'ok':'bad'}'>${fmtUsd(pc.cumPnlUsd)}</td><td>${(pc.positions||[]).length}</td><td>${fmtUsd(pc.walletTotal)}</td></tr>`);
  document.getElementById('channelRows').innerHTML = ch.join('');

  const posRows=[];
  (hl.positions||[]).forEach(p=>{
    posRows.push(`<tr><td>Hyperliquid</td><td>${p.symbol||'-'}</td><td>${p.side||'-'}</td><td>${Number(p.size||0).toFixed(6)}</td><td>${p.leverage||'-'}x</td><td class='${Number(p.unrealizedPnl)>=0?'ok':'bad'}'>${fmtUsd(p.unrealizedPnl)}</td></tr>`);
  });
  (pc.positions||[]).forEach(p=>{
    posRows.push(`<tr><td>Polymarket</td><td>${p.title||p.asset||'-'}</td><td>${p.side||'LONG'}</td><td>${Number(p.qty||0).toFixed(4)}</td><td>${p.leverage||1}x</td><td>${p.pnl===null?'-':fmtUsd(p.pnl)}</td></tr>`);
  });
  if(!posRows.length) posRows.push('<tr><td colspan="6" class="muted">오픈 포지션 없음</td></tr>');
  document.getElementById('posRows').innerHTML = posRows.join('');

  const ops = `
    <div>RPC: <span class='${d.rpc?.ok?'ok':'bad'}'>${d.rpc?.ok?'정상':'오류'}</span> / DEX Pair: ${d.dexPair}</div>
    <div>Polymarket WS: <span class='${d.ws?.ws_connected?'ok':'bad'}'>${d.ws?.ws_connected?'연결됨':'끊김'}</span> (msg ${d.ws?.ws_messages||0})</div>
    <div>Hyperliquid 주소: <span class='mono'>${hl.address||'-'}</span></div>
    <div>Polymarket 카피 실주문: ${pc.executed||0}건, 누적 집행 ${fmtUsd(pc.execUsd)}</div>
  `;
  document.getElementById('ops').innerHTML = ops;
}
setInterval(tick,5000); tick();
</script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")


@app.get("/api/status")
def api_status():
    return jsonify(
        {
            "rpc": rpc_block(),
            "dex": dex_spread(),
            "dexPair": DEX_PAIR,
            "ws": state,
            "hl": hyperliquid_state(),
            "history": load_history(),
            "tradeStats": load_trade_stats(),
            "polymarketCopy": load_polymarket_copy_stats(),
            "paper": {
                **paper,
                "config": {
                    "notionalUsd": PAPER_NOTIONAL_USD,
                    "minSpreadPct": PAPER_MIN_SPREAD_PCT,
                    "captureRatio": PAPER_CAPTURE_RATIO,
                    "costBps": PAPER_COST_BPS,
                },
            },
            "ts": int(time.time()),
        }
    )


if __name__ == "__main__":
    ip = local_ip()
    print("=" * 72)
    print(f"Dashboard local : http://127.0.0.1:{DASHBOARD_PORT}/?token={DASHBOARD_TOKEN}")
    print(f"Dashboard phone : http://{ip}:{DASHBOARD_PORT}/?token={DASHBOARD_TOKEN}")
    print("(same Wi-Fi only. Do NOT port-forward 8788.)")
    print("=" * 72)
    if shutil.which("cloudflared"):
        print("원격(다른 Wi-Fi) 접속: cloudflared tunnel --url http://127.0.0.1:8788")
    else:
        print("다른 Wi-Fi 원격접속은 cloudflared/ngrok 설치 후 터널 사용 권장")

    threading.Thread(target=ws_worker, daemon=True).start()
    threading.Thread(target=paper_worker, daemon=True).start()
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT)
