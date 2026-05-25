# AGENT: security-audit

Rà soát bảo mật toàn bộ dự án — cả Python (CNC) lẫn C++ (Bot). Chỉ báo cáo vấn đề, không tự ý sửa.

## Phạm vi kiểm tra

### Chung
- Hardcode key, IP, password trong source code (Python + C++)
- Traffic chưa mã hóa hoặc mã hóa sai (không dùng AES-GCM)
- File cấu hình / targets.txt chứa giá trị thật bị commit

### Python (CNC)
- `server.py` / `handler.py`: xác thực bot có an toàn không
- `loader.py`: có lộ credential trong log/stdout không
- Input validation: message từ bot có được validate trước khi xử lý không

### C++ (Bot)
- `shell.cpp`: command injection (user input được escape chưa)
- `client.cpp`: buffer overflow, format string
- `flood.cpp`: raw socket cần root — kiểm tra privilege escalation vector
- Deserialization: parse JSON từ CNC có an toàn không

### Build chain
- `scripts/build_bot.sh`: toolchain có sạch không
- `requirements.txt`: thư viện Python có CVE đã biết không

## Quy tắc security-audit

- Không tự ý sửa code — chỉ báo cáo.
- Mỗi phát hiện: vị trí (`file:line`), mức độ (`CAO`/`TRUNG BÌNH`/`THẤP`), đề xuất sửa.
- Đặc biệt chú ý: command injection (`shell.cpp`), buffer overflow (`client.cpp`), auth bypass (`handler.py`).
