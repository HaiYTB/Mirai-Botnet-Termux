#!/bin/bash
# generate_certs.sh — Tạo chứng chỉ TLS tự ký cho CNC server

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$PROJECT_DIR/certs"

mkdir -p "$CERTS_DIR"

echo "[*] Generating self-signed TLS certificate..."

openssl req -x509 -newkey rsa:4096 -keyout "$CERTS_DIR/server.key" \
    -out "$CERTS_DIR/server.crt" -days 365 -nodes \
    -subj "/C=XX/ST=Unknown/L=Unknown/O=CNC/CN=cnc.local" \
    2>/dev/null

echo "[+] Certificate: $CERTS_DIR/server.crt"
echo "[+] Private key:  $CERTS_DIR/server.key"
echo "[+] Valid for:    365 days"
