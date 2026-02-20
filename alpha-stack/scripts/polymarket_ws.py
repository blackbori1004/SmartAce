#!/usr/bin/env python3
import json
import time
from websocket import WebSocketApp

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def on_open(ws):
    print(f"[OPEN] {WS_URL}")
    # Public market stream subscription payload can evolve;
    # keep this minimal and tolerant.
    sub_msg = {
        "type": "subscribe",
        "channel": "market",
    }
    ws.send(json.dumps(sub_msg))
    print("[SUB] market")


def on_message(_ws, message):
    now = time.strftime("%H:%M:%S")
    try:
        data = json.loads(message)
    except Exception:
        print(f"[{now}] raw: {message[:300]}")
        return

    msg_type = data.get("type") or data.get("event") or "unknown"
    # concise console output for live scanning
    print(f"[{now}] {msg_type}: {json.dumps(data)[:260]}")


def on_error(_ws, error):
    print(f"[ERROR] {error}")


def on_close(_ws, code, msg):
    print(f"[CLOSE] code={code}, msg={msg}")


def main():
    ws = WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(ping_interval=20, ping_timeout=10)


if __name__ == "__main__":
    main()
