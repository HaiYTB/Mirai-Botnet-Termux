# AGENT: server-dev

Phát triển phần CNC server + CLI + Loader — **toàn bộ bằng Python**. Đây là trung tâm chỉ huy, chạy trên Termux/VPS của attacker.

## Phạm vi file

| File | Vai trò |
|------|---------|
| `server/server.py` | CNC server chính: lắng nghe kết nối TLS/TCP từ bot, quản lý pool, dispatch lệnh |
| `server/cli.py` | CLI cho attacker: kết nối vào CNC server (Unix socket hoặc TCP local), giao diện tương tác để xem bot, gửi lệnh, xem kết quả |
| `server/loader.py` | SSH/Telnet bulk loader: đọc file `ip:port:user:pass`, kết nối SSH/Telnet, SCP upload bot binary, execute |
| `server/handler.py` | Xử lý giao thức từng bot: xác thực, parse system info (OS/arch/hostname), gửi/nhận message, heartbeat |
| `server/db.py` | SQLite: lưu bot list (id, ip, os, arch, hostname, first_seen, last_seen, status), command history, kết quả |
| `server/commands.py` | Định nghĩa lệnh gửi tới bot (shell_exec, flood_start, flood_stop, steal, recon, ...) |

## Quy tắc server-dev

- Mọi I/O mạng trong `server.py` và `handler.py` là async (`asyncio`).
- Mỗi kết nối bot là một `asyncio.Task` độc lập.
- DB dùng `aiosqlite` để không block event loop.
- **Bot info tracking**: Khi bot auth thành công, nó gửi kèm system info (OS, phiên bản, kiến trúc CPU, hostname, kernel). `handler.py` parse và `db.py` lưu lại.
- **CLI hiển thị bot**: `cli.py` có các lệnh:
  - `bots list` — hiển thị tất cả bot đang online + offline, kèm OS, arch, IP, uptime
  - `bots count` — hiển thị tổng số bot, số online, số offline, phân loại theo OS
  - `bot info <id>` — chi tiết một bot: OS, arch, kernel, hostname, IP, first_seen, last_seen
- `loader.py`:
  - Hỗ trợ cả SSH (`paramiko`) và Telnet (`telnetlib3`)
  - Dùng SCP để upload binary bot (tránh máy không có wget/curl)
  - Đọc targets từ file `ip:port:user:pass` (mỗi dòng 1 target)
  - Chạy đa luồng (`concurrent.futures.ThreadPoolExecutor`)
  - Tự động detect kiến trúc máy nạn nhân (`uname -m`) để chọn binary phù hợp
  - Detect OS (`uname -s`) và phiên bản (`uname -r`), báo cáo về CNC server
- Server phải graceful shutdown (SIGINT/SIGTERM → đóng tất cả kết nối → thoát).
