# R4: CNC server phải dùng asyncio

CNC server (`server/server.py`) bắt buộc dùng `asyncio` để xử lý hàng trăm kết nối bot đồng thời.

**Lý do:** Mô hình thread-per-connection không mở rộng được. Async I/O xử lý được nhiều kết nối hơn với ít tài nguyên hơn.

**Cách áp dụng:**
- `server.py` dùng `asyncio.start_server()`
- `handler.py` là async function
- DB dùng `aiosqlite`
- `cli.py` và `loader.py` là script riêng, không cần async
