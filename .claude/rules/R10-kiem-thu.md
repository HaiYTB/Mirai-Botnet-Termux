# R10: Kiểm thử trước khi merge

- **Python (CNC)**: Test với `pytest` + `pytest-asyncio`. Cấu trúc `tests/` phản chiếu `server/`.
- **C++ (Bot)**: Test từng module riêng trước khi compile. Dùng script test tự động.
- Trước khi commit: `ruff check . && black --check . && pytest`
- Test bot local: chạy CNC server → chạy bot binary local → gửi lệnh → kiểm tra output

**Lý do:** Test phát hiện lỗi sớm, tránh deploy code vỡ lên production.
