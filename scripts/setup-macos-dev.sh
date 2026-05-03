#!/usr/bin/env bash
# One-time setup for macOS development (no Apple cert needed)

set -e

echo "🦾 DClaw Chat — macOS Dev Setup"
echo ""

# Check for Rust
if ! command -v rustc &> /dev/null; then
    echo "📦 Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "✅ Rust installed: $(rustc --version)"
fi

# Check for Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install via: https://nodejs.org"
    exit 1
fi
echo "✅ Node installed: $(node --version)"

# Install Tauri CLI
echo ""
echo "📦 Installing Tauri CLI..."
cargo install tauri-cli --version "^2.0.0-beta"

# Install npm deps
echo ""
echo "📦 Installing npm dependencies..."
cd "$(dirname "$0")/.."
npm install

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Start development server:"
echo "   npm run tauri dev"
echo ""
echo "Build unsigned release:"
echo "   ./scripts/run-unsigned-macos.sh"
echo ""
echo "📝 Apple Developer Cert"
echo "   Not required for development."
echo "   Get one ($99/yr) before App Store distribution:"
echo "   https://developer.apple.com/programs/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
