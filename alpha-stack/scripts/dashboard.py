#!/usr/bin/env python3
import json
import os
import threading
import time
from typing import Any, Dict

import requests
from flask import Flask, jsonify, Response
from websocket import WebSocketApp

app = Flask(__name__)

state: Dict[str, Any] = {
    "ws_connected": False,
    "ws_last_type": None,
    "ws_last_ts": None,
    "ws_messages": 0,
    "ws_error": None,
}

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEX_URL = "https://api.dexscreener.com/latest/dex/search"
DEX_PAIR = os.getenv("DEX_PAIR", "WETH/USDC")


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
    allowed_chains = {"ethereum", "base", "arbitrum", "optimism", "polygon", "bsc", "scroll", "linea", "manta", "soneium", "seiv2", "katana"}
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


@app.get("/")
def index():
    html = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>Alpha Dashboard</title>
  <style>
    body{font-family:system-ui;background:#0b1020;color:#e7ebff;padding:24px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
    .card{background:#141a33;border:1px solid #2a3366;border-radius:12px;padding:16px}
    .ok{color:#42d392}.bad{color:#ff6b6b}
    .muted{color:#95a0d0;font-size:13px}
  </style>
</head>
<body>
  <h2>Alpha Stack Dashboard</h2>
  <div class='muted'>Auto-refresh every 5s</div>
  <div class='grid'>
    <div class='card'><h3>ETH RPC</h3><div id='rpc'></div></div>
    <div class='card'><h3>DEX Spread (<span id='pair'>-</span>)</h3><div id='dex'></div></div>
    <div class='card'><h3>Polymarket WS</h3><div id='ws'></div></div>
  </div>
<script>
async function tick(){
  const r=await fetch('/api/status');
  const d=await r.json();
  const rpc=d.rpc.ok
    ? `<div class='ok'>Connected</div><div>Block: ${d.rpc.block}</div><div class='muted'>${d.rpc.hex}</div>`
    : `<div class='bad'>${d.rpc.error}</div>`;
  document.getElementById('rpc').innerHTML=rpc;

  document.getElementById('pair').textContent = d.dexPair;
  const dex=d.dex.ok
    ? `<div>Spread: <b>${d.dex.spreadPct.toFixed(3)}%</b></div>
       <div>Low: ${d.dex.low.price.toFixed(4)} (${d.dex.low.dex}/${d.dex.low.chain})</div>
       <div>High: ${d.dex.high.price.toFixed(4)} (${d.dex.high.dex}/${d.dex.high.chain})</div>`
    : `<div class='bad'>${d.dex.error}</div>`;
  document.getElementById('dex').innerHTML=dex;

  const ws=`<div class='${d.ws.ws_connected ? 'ok':'bad'}'>${d.ws.ws_connected ? 'Connected':'Disconnected'}</div>
            <div>Messages: ${d.ws.ws_messages}</div>
            <div>Last type: ${d.ws.ws_last_type || '-'}</div>
            <div class='muted'>Last ts: ${d.ws.ws_last_ts || '-'}</div>
            <div class='muted'>Err: ${d.ws.ws_error || '-'}</div>`;
  document.getElementById('ws').innerHTML=ws;
}
setInterval(tick,5000); tick();
</script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")


@app.get("/api/status")
def api_status():
    return jsonify({"rpc": rpc_block(), "dex": dex_spread(), "dexPair": DEX_PAIR, "ws": state, "ts": int(time.time())})


if __name__ == "__main__":
    t = threading.Thread(target=ws_worker, daemon=True)
    t.start()
    app.run(host="127.0.0.1", port=8788)
