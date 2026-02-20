#!/usr/bin/env python3
import argparse
import time
import requests

# DexScreener: public endpoint, no key required
URL = "https://api.dexscreener.com/latest/dex/search"


def fetch_pairs(pair_query: str):
    r = requests.get(URL, params={"q": pair_query}, timeout=12)
    r.raise_for_status()
    data = r.json()
    return data.get("pairs", [])


ALLOWED_CHAINS = {"ethereum", "base", "arbitrum", "optimism", "polygon", "bsc", "scroll", "linea", "manta", "soneium", "seiv2", "katana"}


def normalize(pair):
    return {
        "dex": pair.get("dexId"),
        "chain": pair.get("chainId"),
        "pair": pair.get("pairAddress"),
        "price": float(pair.get("priceUsd") or 0),
        "liquidity": float((pair.get("liquidity") or {}).get("usd") or 0),
        "volume24h": float((pair.get("volume") or {}).get("h24") or 0),
        "base": ((pair.get("baseToken") or {}).get("symbol") or "").upper(),
        "quote": ((pair.get("quoteToken") or {}).get("symbol") or "").upper(),
        "url": pair.get("url"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="ETH/USDC", help="e.g. ETH/USDC")
    ap.add_argument("--interval", type=int, default=10, help="seconds")
    ap.add_argument("--min-liquidity", type=float, default=100000, help="USD")
    args = ap.parse_args()

    print(f"Monitoring {args.pair} every {args.interval}s (min liquidity ${args.min_liquidity:,.0f})")

    want_base, want_quote = [x.strip().upper() for x in args.pair.split("/")]
    base_alias = {want_base, "WETH"} if want_base == "ETH" else {want_base}
    quote_alias = {want_quote, "USDC.E", "USDB"} if want_quote == "USDC" else {want_quote}

    while True:
        try:
            raw = fetch_pairs(args.pair)
            rows = [normalize(p) for p in raw]
            rows = [
                r
                for r in rows
                if r["price"] > 0
                and r["liquidity"] >= args.min_liquidity
                and r["chain"] in ALLOWED_CHAINS
                and r["base"] in base_alias
                and r["quote"] in quote_alias
            ]
            if len(rows) < 2:
                print("Not enough liquid pairs yet...")
                time.sleep(args.interval)
                continue

            rows.sort(key=lambda x: x["price"])
            low = rows[0]
            high = rows[-1]
            spread_pct = ((high["price"] - low["price"]) / low["price"]) * 100

            ts = time.strftime("%H:%M:%S")
            print(
                f"[{ts}] low={low['price']:.4f} ({low['dex']}:{low['chain']}) | "
                f"high={high['price']:.4f} ({high['dex']}:{high['chain']}) | "
                f"spread={spread_pct:.3f}%"
            )

            if spread_pct >= 0.35:
                print("  -> SIGNAL: potential arb window (check fees/gas/slippage before action)")

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
