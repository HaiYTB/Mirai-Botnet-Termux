# R8: Phong cách code

**Python (CNC):**
- PEP 8, `ruff` + `black`
- `snake_case` hàm/biến, `PascalCase` class, `UPPER_CASE` hằng số
- Không comment thừa — chỉ giải thích WHY

**C++ (Bot):**
- C++17, `snake_case` hàm/biến, `PascalCase` class/struct
- Hạn chế include nặng, ưu tiên header-only library
- Không dùng exception nếu không cần (tránh RTTI overhead)
- Compile flag: `-std=c++17 -O2 -static -s -fno-exceptions -fno-rtti`
- Không comment thừa

**Lý do:** Code sạch, nhẹ, đồng nhất giữa hai ngôn ngữ.
