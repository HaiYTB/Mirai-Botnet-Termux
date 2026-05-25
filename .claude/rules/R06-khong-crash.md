# R6: Xử lý lỗi không được crash

CNC server và bot client không được crash vì bất kỳ lý do gì. Bọc tất cả vòng lặp chính trong try/catch.

**Lý do:** Server crash = mất toàn bộ mạng bot. Bot crash = mất quyền kiểm soát máy đó.

**Cách áp dụng:**
- Python: `while True: try: ... except Exception: logger.error(...)`
- C++: `while (running) { try { ... } catch (const std::exception& e) { ... } catch (...) { ... } }`
- Bot phải reconnect với exponential backoff (1s → 2s → 4s → ... max 300s)
- CNC server phải graceful shutdown (SIGINT → đóng tất cả kết nối → thoát)
