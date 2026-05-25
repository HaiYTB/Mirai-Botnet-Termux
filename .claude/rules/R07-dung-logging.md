# R7: Dùng logging, không dùng print/printf

- **Python (CNC)**: Dùng module `logging`. Format: `[%(asctime)s] %(levelname)s: %(message)s`
- **C++ (Bot)**: Log ra stderr (syslog nếu có), không dùng `printf`/`cout` trực tiếp

**Lý do:** Log có timestamp và log level giúp debug và vận hành. Bot nên log tối thiểu để tránh forensic.

**Cách áp dụng:**
- Python: `logger = logging.getLogger(__name__)` trong mỗi file
- C++: Define macro `LOG(level, msg, ...)` ghi ra stderr với timestamp
- Bot chỉ log ở mức ERROR, CNC log đầy đủ
