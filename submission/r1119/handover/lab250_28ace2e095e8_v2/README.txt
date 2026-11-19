Release: lab250_28ace2e095e8_v2
Parent: lab250_28ace2e095e8
Số ảnh: 243
Số nhãn: 1676
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 13/250 = 5,2%
Kết luận v1: Hold — 13/250 = 5.2% vượt ngưỡng 2%
Kết luận v2: Release — tách 7 ảnh lỗi nhãn detection sang rework, sửa split/hash/guideline; còn 2 ảnh lỗi panoptic ở lại (nhãn detection đúng)
Ghi chú: scene_leak scene_302: cả cảnh đưa về một split (split đa số của cảnh) trong truyvet.csv. wrong_hash 000000025096: đã mở ảnh (giải mã được, đúng kích thước), chỉ manifest v1 sai, manifest.csv v2 ghi hash mới. guideline_mismatch 000000009483, 000000013291: truyvet.csv ghi guideline theo job trong jobs.csv. Rework 7 ảnh giao lại đúng người gán/kiểm của job (A01: 2, A02: 3, A03: 1, A05: 1). Lỗi chỉ ở panoptic (ảnh ở lại v2, báo team panoptic): 000000007574, 000000025228.
