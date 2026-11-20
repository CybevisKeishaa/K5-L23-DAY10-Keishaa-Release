# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Keishaa | Claude Code (Claude Opus) | "Đọc plan.md (QC đề ẩn Day 10) rồi hướng dẫn cho tôi các step để làm" — AI đọc RULES/GUIDE/DELIVERY, viết `validator/validate.py` (9 luật + ứng viên), `validator/trace_query.py` | Bản đầu nhận ca gộp segment (`instance_merge`) thành `bbox_drift`, vì pixel tràn ra ngoài box đã ghép | Viết `tests/test_validator.py` tự gài lỗi vào bản sao lô sạch; thêm luật "pixel tràn rơi vào box cùng lớp khác ⇒ gộp"; test PASS |
| 2 | Keishaa | Claude Code | Đo ngưỡng ứng viên trên lô sạch và lô kiểu đề ẩn | Ngưỡng `cov < 0.9` ban đầu bỏ sót box lệch nhỏ (profile lệch 6–15%) | Quét 0.90/0.95/0.97/0.98 trên lô sạch (0 ứng viên mọi mức) rồi chọn 0.97; số liệu ở REPORT mục 1 |
| 3 | Keishaa | Claude Code | Viết công cụ xem ảnh `tools/review_tool.py` (Pillow), `tools/build_v2.py`, `tools/finalize.py`, `tools/run_hidden.py` | — | Chạy `check_handover.py` bản gốc: 16/17 PASS trước review (H3 chờ người xem ảnh) |
| 4 | Keishaa | Claude Code | Cho tôi path đến ảnh có mặt người cho `security.md` | AI tự mở 3 ảnh COCO công khai (000000004395, 000000001296, 000000016598) để chọn ví dụ | Keishaa tự mở lại cả 3 ảnh: đúng là mặt người nhìn rõ như mô tả trong `security.md` |
| 5 | Keishaa | Claude Code | Kiểm `de_an/review_log.csv` do nhóm xuất từ `review.html` | Nhóm chọn `category_swap` cho img_0076 và img_0174 dù detection mới là bên sai; AI tự mở ảnh, cắt phóng to img_0174, đổi cả hai thành `class_swap` và viết lại ghi chú img_0174 | Keishaa tự mở lại img_0174 (ảnh gốc + bản phóng to): xác nhận là túi xách tay (handbag), không phải vali ⇒ giữ `class_swap`; sửa `review_tool.py` để mỗi loại lỗi ghi rõ bên nào sai |
| 6 | Keishaa | Claude Code | Kiểm `r1119/review_log.csv` (Keishaa xem cả 7 ảnh, xuất từ `review.html`) | Không (AI không mở ảnh): AI chỉ ra loại lỗi lệch với ghi chú ở 000000018833, 000000012670, 000000018380 | Keishaa trả lời lại từng ảnh (mèo ⇒ `class_swap`; ba lô ⇒ `class_swap`; box lệch ⇒ `bbox_drift`); AI viết lại ghi chú theo câu trả lời; `check_handover.py` 17 PASS |

Ngoài dòng 5 (img_0076, img_0174 của đề ẩn), AI **không** điền kết luận `confirmed`/`rejected` nào trong `review_log.csv`: mọi kết luận do người xem ảnh bằng `review.html`.
