Release: lab250_28ace2e095e8_v2
Parent: lab250_28ace2e095e8
Số ảnh: 237
Số nhãn: 1584
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 20/250 = 8,0%
Kết luận v1: Hold — 20/250 = 8.0% vượt ngưỡng 2%
Kết luận v2: Release — tách 13 ảnh lỗi nhãn detection sang rework, sửa split/hash/guideline; còn 3 ảnh lỗi panoptic ở lại (nhãn detection đúng)
Ghi chú: scene_leak scene_302: cả cảnh đưa về một split (split đa số của cảnh) trong truyvet.csv. wrong_hash 000000025096: đã mở ảnh (giải mã được, đúng kích thước), chỉ manifest v1 sai, manifest.csv v2 ghi hash mới. guideline_mismatch 000000009483, 000000013291: truyvet.csv ghi guideline theo job trong jobs.csv. Rework 13 ảnh giao lại đúng người gán/kiểm của job (A01: 2, A02: 4, A03: 1, A04: 3, A05: 3). Lỗi chỉ ở panoptic (ảnh ở lại v2, báo team panoptic): 000000001993, 000000007574, 000000025228.
