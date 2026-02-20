#!/usr/bin/env python3
import json
import os
import requests


def check_rpc(name: str, url: str):
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        block_hex = data.get("result")
        if not block_hex:
            print(f"[FAIL] {name}: no result -> {data}")
            return False
        block = int(block_hex, 16)
        print(f"[OK]   {name}: block {block} ({block_hex})")
        return True
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        return False


def main():
    targets = {
        "ETH_RPC_URL": os.getenv("ETH_RPC_URL"),
        "BASE_RPC_URL": os.getenv("BASE_RPC_URL"),
        "ARB_RPC_URL": os.getenv("ARB_RPC_URL"),
    }

    print("RPC connectivity check")
    print("-" * 40)

    any_set = False
    ok = True
    for name, url in targets.items():
        if url:
            any_set = True
            ok = check_rpc(name, url) and ok
        else:
            print(f"[SKIP] {name}: not set")

    if not any_set:
        print("\nNo RPC URLs set. Export ETH_RPC_URL first.")
        raise SystemExit(1)

    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
