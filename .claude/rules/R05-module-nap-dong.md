# R5: Module payload là binary riêng biệt

Mỗi module bot (shell, flood, steal, recon) là một **binary C++ riêng**, bot chính (`client`) gọi tới qua `fork()/exec()` hoặc `system()`.

**Lý do:**
- Module độc lập dễ compile, dễ thay thế
- Nếu 1 module bị crash, bot chính không chết
- Có thể upload module mới lên bot đang chạy mà không cần build lại toàn bộ

**Cách áp dụng:**
- Mỗi module compile thành 1 file binary riêng trong thư mục modules/
- `client` nhận lệnh từ CNC, parse module name + params, gọi `popen()` hoặc `fork()+exec()`
- Output từ module được capture và gửi về CNC
