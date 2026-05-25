# AGENT: test-writer

Viết test cho cả Python (CNC) và C++ (Bot).

## Phạm vi file

| Thư mục test | Bao phủ |
|--------------|---------|
| `tests/test_server/` | Test `server.py`, `handler.py`, `db.py`, `commands.py` |
| `tests/test_loader/` | Test `loader.py`: SSH mock, SCP mock, parser targets.txt |
| `tests/test_shared/` | Test protocol framing, AES-GCM encrypt/decrypt |
| `tests/test_bot/` | Test script build, test từng module C++ riêng |

## Quy tắc test-writer

### Python
- `pytest` + `pytest-asyncio` cho async test
- Mỗi file `server/X.py` → `tests/test_server/test_X.py`
- Mock network connection để test handler không cần bot thật

### C++
- Mỗi module `bot/modules/X.cpp` compile riêng với `-DTEST` flag
- Test script: `scripts/test_bot.sh` build + chạy từng module với input mẫu
- So sánh output thực tế với expected

### Protocol cross-test (quan trọng nhất)
- Test gửi message từ Python → C++ parse (và ngược lại)
- Đảm bảo AES-GCM encrypt/decrypt tương thích 2 bên
- Test replay attack: gửi message cũ → phải bị từ chối

### Coverage
- Python: tối thiểu 70% cho `server/` và `shared/`
- C++: mỗi module có ít nhất 1 test case happy path
