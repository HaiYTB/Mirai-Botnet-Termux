# R1: Mã hóa toàn bộ traffic C2

Tất cả giao tiếp giữa CNC server (Python) và bot (C++) phải được mã hóa. Dùng AES-GCM với pre-shared key. **Không bao giờ** gửi plaintext qua mạng.

**Lý do:** Traffic không mã hóa dễ bị IDS/IPS phát hiện. Botnet không mã hóa = bị bắt ngay.

**Cách áp dụng:**
- Python side (`shared/crypto.py`): `encrypt(plaintext, key) -> iv+ciphertext+tag`
- C++ side (`bot/common.h`): implement AES-GCM dùng OpenSSL hoặc tiny-AES-c (header-only)
- Key nằm trong config, KHÔNG hardcode vào source C++
