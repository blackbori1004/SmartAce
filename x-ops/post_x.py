#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from requests_oauthlib import OAuth1


def load_env(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def require(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise ValueError(f"missing required env: {name}")
    return v


def post_tweet(text: str, dry_run: bool = False) -> dict:
    api_key = require("X_API_KEY")
    api_secret = require("X_API_SECRET")
    access_token = require("X_ACCESS_TOKEN")
    access_secret = require("X_ACCESS_TOKEN_SECRET")

    if len(text) > 280:
        raise ValueError(f"tweet too long: {len(text)} chars (max 280)")

    payload = {"text": text}
    if dry_run:
        return {"dry_run": True, "payload": payload}

    auth = OAuth1(api_key, api_secret, access_token, access_secret)
    r = requests.post(
        "https://api.twitter.com/2/tweets",
        auth=auth,
        json=payload,
        timeout=20,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.status_code >= 300:
        raise RuntimeError(f"X API error {r.status_code}: {json.dumps(data, ensure_ascii=False)}")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description="Post approved text to X")
    p.add_argument("--env-file", default="x-ops/.env.x", help="Path to env file")
    p.add_argument("--text", help="Tweet text")
    p.add_argument("--text-file", help="Read tweet text from file")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.text and not args.text_file:
        print("Provide --text or --text-file", file=sys.stderr)
        return 2

    load_env(Path(args.env_file))

    text = args.text
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    assert text is not None

    try:
        out = post_tweet(text, dry_run=args.dry_run)
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
