#!/usr/bin/env bash
# Run unsigned DClaw Chat on macOS
# This script builds and launches the app without code signing

set -e

echo "🔨 Building DClaw Chat (unsigned)..."
echo "   Note: First run requires Gatekeeper bypass."
echo ""

# Build the Tauri app without signing
cd "$(dirname "$0")/.."
npm run tauri build -- --no-bundle-sign 2>/dev/null || npm run tauri build

APP_PATH="src-tauri/target/release/bundle/macos/DClaw Chat.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Build failed or app not found at: $APP_PATH"
    exit 1
fi

echo ""
echo "✅ Build complete"
echo ""
echo "📁 App location: $APP_PATH"
echo ""
echo "🚀 Launching..."
echo ""

# Remove quarantine attribute if present (allows unsigned apps to run)
xattr -rd com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# Open the app
open "$APP_PATH"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "If the app doesn't open:"
echo ""
echo "1. Open System Settings → Privacy & Security"
echo "2. Scroll to 'Security' section"
echo "3. Click 'Open Anyway' next to 'DClaw Chat'"
echo ""
echo "Or run this command:"
echo "   xattr -rd com.apple.quarantine \"$APP_PATH\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
