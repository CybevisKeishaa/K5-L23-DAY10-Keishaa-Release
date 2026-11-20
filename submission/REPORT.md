# Báo cáo nhóm Keishaa

> Làm một mình (lớp hết slot nhóm, đã xin phép giảng viên). Seed luyện tập: **1119**. Mọi số dưới đây lấy từ lần chạy thật trên máy (`runs/`, không commit); `score_findings.py` chỉ in F1 làm tròn 1 chữ số.

## 1. Số liệu luyện tập

**Lỗi luật** (`validator/validate.py`, chỉ đọc `delivery/`, thư viện chuẩn + `scripts/pngutil.py`):

| Lô | Lỗi luật báo | F1 luật |
|---|---:|---:|
| r1119 (seed nộp) | 13 | ≈ 1.0 |
| seed phụ 11 / 22 / 33 / 44 / 55 | 13 / 9 / 12 / 9 / 10 | ≈ 1.0 cả 5 |
| 3 lô tự tạo kiểu đề ẩn (`--opaque`, profile lệch box 6–15%, đổi lớp toàn lớp dễ nhầm) | 14 / 12 / 9 | ≈ 1.0 cả 3 |
| lô sạch `--no-faults` (50 ảnh calib) | **0** | — |

**Ứng viên lỗi gán nhãn** (chưa qua review, đổi tạm `class_mismatch` → `class_swap` để tự đo):

| Lô | Ứng viên | F1 gán nhãn nếu nộp hết ứng viên |
|---|---:|---:|
| r1119 | 7 (trên 7 ảnh) | sau review: 7 confirmed, 0 rejected (xem dưới) |
| seed 11 / 22 / 33 / 44 / 55 | 5 / 7 / 8 / 6 / 10 | ≈ 0.6 / 0.5 / 0.8 / 0.8 / 0.8 |
| 3 lô kiểu đề ẩn | 10 / 6 / 8 | ≈ 0.7 / 0.5 / 0.7 |
| lô sạch | **0** | — |

- F1 seed 1119 sau review (`score_findings.py`, 20 lỗi nộp): tổng ≈ 0.9 · luật ≈ 1.0 · gán nhãn ≈ 0.9 · truy vết tier_a/tier_b/notify ≈ 1.0. Review: 2 `class_swap`, 1 `category_swap`, 3 `bbox_drift`, 1 `missing_box`.
- Hàng đợi review seed 1119: **7 ảnh** (3 lệch lớp, 3 box lệch, 1 thiếu box).

**Cách ghép và chọn ngưỡng (không dùng `_private`):**
- Ghép box ↔ segment thing (bỏ `iscrowd`) qua **tên lớp**, tham lam theo IoU (box, bbox của mask): cùng lớp IoU ≥ 0.3 trước, rồi khác lớp IoU ≥ 0.6 (ra ứng viên lệch lớp; `class_swap` hay `category_swap` do người xem ảnh quyết).
- Tín hiệu chính là **pixel mask**: `cov` = tỉ lệ pixel của segment nằm trong box. COCO tự nhiên có cov ≈ 1 vì mask nằm trong box gốc. Quét ngưỡng `cov < 0.90 / 0.95 / 0.97 / 0.98` trên lô sạch: **0 ứng viên ở mọi mức**; seed 1119 giữ nguyên 7; lô lệch nhỏ (h101) tăng 7 → 10 và F1 tự đo 0.6 → 0.7. Chọn **0.97** (còn biên so với 0.98).
- Pixel tràn khỏi box mà ≥ 50% rơi vào một box **cùng lớp khác** ⇒ `instance_merge` thay vì `bbox_drift`.
- Segment ≥ 0.5% ảnh không có box cùng lớp nào IoU ≥ 0.3 ⇒ `missing_box`; nếu có box cùng lớp chưa ghép nằm đè lên thì là box lệch xa ⇒ `bbox_drift`.
- Ảnh đã có lỗi luật thì bỏ ứng viên (DELIVERY.md: mỗi ảnh nhiều nhất một lỗi).
- `duplicate_box`: cùng lớp, cùng kích thước (lệch ≤ 0.5 px), tâm lệch ≤ 3 px mỗi trục — không dùng IoU nên không bắt nhầm cặp tự nhiên IoU ~0.66. `bbox_out_of_bounds`: tràn > 0.5 px. `thing_overlap`: `area` khai > số pixel đếm được trong mask.
- Kiểm thêm bằng fixture tự gài (`tests/test_validator.py`): gài đủ 9 lỗi luật + 4 kiểu ứng viên vào bản sao lô sạch ⇒ bắt đủ, lô sạch im lặng, chạy lại ra y hệt.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
F1 là trung bình điều hoà của precision và recall trên cặp `(type, target)`; báo thừa bị trừ như bỏ sót. Mỗi ứng viên chưa xem mà nộp luôn thì hoặc đúng, hoặc thành FP. Ví dụ đo được: nộp hết ứng viên ở seed 22 cho F1 gán nhãn chỉ ≈ 0.5 — một phần vì mỗi ca lệch lớp chỉ có **một** trong hai giả thuyết (`class_swap` / `category_swap`) đúng, đoán sai loại thì vừa FP vừa FN. Với lô thật, COCO còn có lệch tự nhiên (vật bị che, crowd) nên ghép thô sinh nhiều ứng viên hơn số lỗi; nộp hết thì precision tụt và kéo F1 xuống, nên phải xem ảnh để `rejected` ca tự nhiên và chọn đúng loại.

## 3. Quyết định và lineage
QC v1 = **20/250 = 8,0%** (13 lỗi luật + 7 lỗi gán nhãn đã xác nhận) > ngưỡng 2% ⇒ **HOLD** (đã ghi `decision HOLD` cho `lab250_28ace2e095e8`). `lineage.py impact` trả `R-021: affected=True action=review_or_retrain`: R-021 đã train trên v1 có lỗi; đổi dataset không tự sửa model đã học, nên phải đánh giá lại R-021 trên dữ liệu sạch hoặc train lại trên v2. v2 ghi `release lab250_28ace2e095e8_v2 --parent lab250_28ace2e095e8`: 237 ảnh, 1584 nhãn, 13 ảnh vào `rework_queue.csv`; `check_handover.py` 17 PASS.

## 4. Hash chứng minh gì, không chứng minh gì?
sha256 chứng minh **byte** của file không đổi từ lúc lập manifest (v1 không bị ghi đè, zip v2 tái lập đúng mã `.sha256`), và phát hiện file bị thay (ca `wrong_hash` 000000025096: hash trong manifest là của ảnh khác; mở ảnh thấy giải mã được, đúng kích thước nên chỉ manifest sai, v2 ghi hash mới). Hash **không** chứng minh nhãn đúng (box lệch hay sai lớp vẫn có hash hợp lệ), không chứng minh ảnh đúng nội dung/đúng cảnh, không cho biết ai gán và gán theo guideline nào.

## 5. Truy vết
Changelog v1.3 đổi quy tắc lớp **`wine glass`**; ticket nêu `scene_184`, `scene_397`. Job guideline cũ (theo `jobs.csv`): J01–J04. `tier_a` = ảnh trong hai cảnh đó, thuộc job cũ, có ≥ 1 box `wine glass` trong `labels/` (3 ảnh); `tier_b` = ảnh khác cùng điều kiện (4 ảnh); `notify` = người gán + người kiểm của các job đó: A03, A04, Q01, Q02. Lấy guideline **theo job**, không theo metadata ảnh, vì guideline ở từng ảnh có thể chính là lỗi `guideline_mismatch` (seed này có 2 ảnh như vậy). Tự đo (`score_findings.py`): tier_a ≈ 1.0, tier_b ≈ 1.0, notify ≈ 1.0.

## 6. Bug hoặc điểm chưa rõ trong lab
Không tìm thấy bug trong `scripts/`. Không sửa script nào.
