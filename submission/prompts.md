# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | <<tên>> | Claude Code (Claude Opus) | "Đọc plan.md (QC đề ẩn Day 10) rồi làm bài lab đến khi xong" — AI đọc RULES/GUIDE/DELIVERY, viết `validator/validate.py` (9 luật + ứng viên), `validator/trace_query.py` | Bản đầu nhận ca gộp segment (`instance_merge`) thành `bbox_drift`, vì pixel tràn ra ngoài box đã ghép | Viết `tests/test_validator.py` tự gài lỗi vào bản sao lô sạch; thêm luật "pixel tràn rơi vào box cùng lớp khác ⇒ gộp"; test PASS |
| 2 | <<tên>> | Claude Code | Đo ngưỡng ứng viên trên lô sạch và lô kiểu đề ẩn | Ngưỡng `cov < 0.9` ban đầu bỏ sót box lệch nhỏ (profile lệch 6–15%) | Quét 0.90/0.95/0.97/0.98 trên lô sạch (0 ứng viên mọi mức) rồi chọn 0.97; số liệu ở REPORT mục 1 |
| 3 | <<tên>> | Claude Code | Viết công cụ xem ảnh `tools/review_tool.py` (Pillow), `tools/build_v2.py`, `tools/finalize.py`, `tools/run_hidden.py` | — | Chạy `check_handover.py` bản gốc: 16/17 PASS trước review (H3 chờ người xem ảnh) |
| 4 | <<tên>> | Claude Code | Chọn ảnh có mặt người cho `security.md` | AI tự mở 3 ảnh COCO công khai (000000004395, 000000001296, 000000016598) để chọn ví dụ | <<người tự mở lại 3 ảnh này và xác nhận>> |

AI **không** điền dòng `confirmed`/`rejected` nào trong `review_log.csv`: mọi kết luận do người xem ảnh bằng `review.html`.
