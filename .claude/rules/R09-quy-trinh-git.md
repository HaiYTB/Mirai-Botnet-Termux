# R9: Quy trình Git

- `main` là nhánh ổn định. Tạo nhánh tính năng từ `main`.
- Commit message bằng **tiếng Anh**, thể mệnh lệnh: `add flood module`, `fix loader timeout`
- **Không commit:** config.yaml, targets.txt, key, cert, binary file trong `dist/`
- File `.gitignore` đã có sẵn — đảm bảo `dist/` và `*.o` được ignore

**Lý do:** Lịch sử rõ ràng, không lộ secret, repo sạch (chỉ chứa source).
