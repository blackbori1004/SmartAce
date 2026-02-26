#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 'tweet text'" >&2
  exit 2
fi

TEXT="$1"
python3 /Users/bori/.openclaw/workspace/x-ops/post_x.py \
  --env-file /Users/bori/.openclaw/workspace/x-ops/.env.x \
  --text "$TEXT"
