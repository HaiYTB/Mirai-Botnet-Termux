# R2: Không hardcode giá trị nhạy cảm

Không hardcode key, IP, port vào source code (cả Python lẫn C++). Mọi giá trị từ config file hoặc truyền qua command-line args.

**Lý do:** Hardcode gây rủi ro lộ thông tin khi commit, khó triển khai lại.

**Cách áp dụng:**
- Python: load từ `config.yaml` hoặc env vars
- C++: nhận qua `argv` hoặc embedded config được inject lúc build (`scripts/build_bot.sh`)
- File `targets.txt` (ip:port:user:pass) không bao giờ commit
