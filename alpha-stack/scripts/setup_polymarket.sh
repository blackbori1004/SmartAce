#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

# py-clob-client dependency chain currently fails on this host's Python 3.9.6
# unless we bypass requires-python and install from Polymarket repos directly.
pip install --ignore-requires-python \
  'git+https://github.com/Polymarket/poly-py-eip712-structs.git' \
  'git+https://github.com/Polymarket/python-order-utils.git' \
  'git+https://github.com/Polymarket/py-clob-client.git' \
  python-dotenv

echo "[ok] polymarket client deps installed"
