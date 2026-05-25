# R3: Bot là C++ static binary, không Python

Bot và tất cả module payload phải viết bằng C++, compile thành **static binary** (link tĩnh). Không dùng Python cho bot.

**Lý do:** Máy nạn nhân thường không có Python, không có thư viện. Static binary chạy được trên mọi Linux mà không cần bất kỳ dependency nào.

**Cách áp dụng:**
- Compile với `-static -s` (static link + strip symbol)
- Dùng `musl-gcc` hoặc `-static-libstdc++ -static-libgcc`
- Cross-compile sẵn cho arm/aarch64/x86/x86_64/mips/mipsel
- Python CHỈ dùng cho CNC server, CLI, và loader
