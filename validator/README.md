# Validator của nhóm

Viết `validate.py` ở đây. Giao diện cố định:

```
python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

Chỉ đọc thư mục delivery được truyền vào; chỉ thư viện chuẩn; không mạng. Xem [GUIDE.md](../GUIDE.md) Pha 1–2 và [RULES.md](../RULES.md).

## Đề ẩn trong 40 phút (đã diễn tập: ~5 giây/đề)

```bash
py -X utf8 tools/run_hidden.py de_an.zip --assign <mã_đề>   # giải nén an toàn (bỏ _private), validator, trace, review.html
# NGƯỜI mở runs/day10_hidden/<zip>/<mã_đề>/review/review.html, xem từng ảnh, bấm "Tải review_log.csv",
# chép file vào submission/de_an/review_log.csv
py -X utf8 tools/finalize.py --de-an <đường dẫn delivery in ở bước 1>   # errors.json = luật + confirmed; trace.json
```

Seed luyện tập: sau khi lưu `runs/r1119/review_log.csv`, chạy `py -X utf8 tools/finalize.py --run runs/r1119`
(merge → v2 → pack → lineage → `check_handover.py` → export sang `submission/`).
