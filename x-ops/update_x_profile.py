#!/usr/bin/env python3
import argparse
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


def main() -> int:
    p = argparse.ArgumentParser(description="Update X profile bio")
    p.add_argument("--env-file", default="x-ops/.env.x")
    p.add_argument("--description", required=True)
    args = p.parse_args()

    load_env(Path(args.env_file))

    api_key = require("X_API_KEY")
    api_secret = require("X_API_SECRET")
    access_token = require("X_ACCESS_TOKEN")
    access_secret = require("X_ACCESS_TOKEN_SECRET")

    auth = OAuth1(api_key, api_secret, access_token, access_secret)
    r = requests.post(
        "https://api.twitter.com/1.1/account/update_profile.json",
        auth=auth,
        data={"description": args.description},
        timeout=20,
    )

    if r.status_code >= 300:
        print(r.text, file=sys.stderr)
        return 1

    print(r.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
