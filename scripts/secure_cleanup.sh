#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/Users/bori/.openclaw/workspace"

# Remove stale logs/tmp older than 7 days inside workspace only
find "$WORKSPACE" -type f \( -name "*.log" -o -name "*.tmp" -o -name "*.temp" \) -mtime +7 -delete 2>/dev/null || true
find "$WORKSPACE" -type d \( -name "tmp" -o -name ".cache" \) -prune -exec rm -rf {} + 2>/dev/null || true

# Tighten permissions for env files if present
find "$WORKSPACE" -type f \( -name ".env" -o -name ".env.*" \) -exec chmod 600 {} \; 2>/dev/null || true
