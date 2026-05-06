#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-chat.dclawstack.io}"
DPANEL_DIR="${2:-../dclaw-platform/dpanel}"

if [ ! -d "$DPANEL_DIR" ]; then
  echo "❌ DPanel not found at $DPANEL_DIR"
  exit 1
fi

sed -i "s|domain: \"localhost:30002\"|domain: \"$DOMAIN\"|" "$DPANEL_DIR/lib/apps.ts"
echo "✅ Updated DPanel domain to $DOMAIN"
