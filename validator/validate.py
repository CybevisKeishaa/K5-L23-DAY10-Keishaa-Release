#!/usr/bin/env python3
"""Validator Day 10: lỗi luật (9 loại) + ứng viên lỗi gán nhãn (đối chiếu detection <-> panoptic).

  python validator/validate.py <delivery> --out rules.json [--candidates candidates.json]

- Chỉ đọc thư mục delivery được truyền vào. Chỉ thư viện chuẩn + scripts/pngutil.py. Không mạng.
- --out chỉ chứa lỗi LUẬT (máy chứng minh được). Lỗi gán nhãn chỉ là ứng viên trong --candidates;
  người xem ảnh rồi ghi review_log.csv, sau đó gộp bằng scripts/merge_review.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402

# Ngưỡng chọn bằng cách đo trên lô sạch (pool calib) và seed luyện tập, xem submission/REPORT.md.
OOB_TOL_PX = 0.5          # box tràn mép > 0.5 pixel là lỗi
DUP_SIZE_PX = 0.5         # duplicate: cùng kích thước (lệch <= 0.5 px)
DUP_SHIFT_PX = 3.0        # duplicate: tâm lệch <= 3 px mỗi trục
MATCH_IOU = 0.3           # ghép box <-> segment cùng lớp
SWAP_IOU = 0.6            # ghép box <-> segment KHÁC lớp (ứng viên class/category swap)
DRIFT_COV = 0.97          # < 97% pixel segment nằm trong box đã ghép => ứng viên bbox_drift (lô sạch: 0 ca tới 0.98)
MISSING_AREA = 0.005      # segment thing >= 0.5% ảnh mà không box cùng lớp nào => ứng viên missing_box
MERGE_FILL = 0.3          # box cùng lớp không ghép được nhưng >= 30% diện tích là pixel của segment khác


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def parse_labels(text: str):
    """Trả về list (dòng, class_id|None, x, y, w, h); class_id None nếu không đọc được."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        try:
            cls_f = float(parts[0])
            cls = int(cls_f) if cls_f.is_integer() else None
            x, y, w, h = (float(v) for v in parts[1:5])
            if len(parts) < 5:
                raise ValueError
        except ValueError:
            rows.append((n, None, 0.0, 0.0, 0.0, 0.0))
            continue
        rows.append((n, cls, x, y, w, h))
    return rows


def mask_runs(path: Path):
    """Một lần đọc mask: segment id -> list run (y, x0, x1) cùng số pixel và bbox [x0,y0,x1,y1] (bao gồm)."""
    width, height, px = pngutil.read_rgb(path)
    runs, count, bbox = {}, {}, {}
    stride = width * 3
    for y in range(height):
        base = y * stride
        start, cur = 0, px[base] | px[base + 1] << 8 | px[base + 2] << 16
        for x in range(1, width + 1):
            if x < width:
                i = base + 3 * x
                sid = px[i] | px[i + 1] << 8 | px[i + 2] << 16
                if sid == cur:
                    continue
            if cur:
                runs.setdefault(cur, []).append((y, start, x - 1))
                count[cur] = count.get(cur, 0) + x - start
                b = bbox.get(cur)
                if b is None:
                    bbox[cur] = [start, y, x - 1, y]
                else:
                    b[0], b[1], b[2], b[3] = min(b[0], start), min(b[1], y), max(b[2], x - 1), max(b[3], y)
            if x < width:
                start, cur = x, sid
    return width, height, runs, count, bbox


def inside(runs, box_px) -> int:
    """Số pixel (theo tâm pixel) của segment nằm trong box [x0,y0,x1,y1] (toạ độ thực)."""
    bx0, by0 = math.ceil(box_px[0] - 0.5), math.ceil(box_px[1] - 0.5)
    bx1, by1 = math.floor(box_px[2] - 0.5), math.floor(box_px[3] - 0.5)
    total = 0
    for y, x0, x1 in runs:
        if by0 <= y <= by1:
            lo, hi = max(x0, bx0), min(x1, bx1)
            if hi >= lo:
                total += hi - lo + 1
    return total


def analyze(job: dict) -> dict:
    """Chạy trong process riêng cho một ảnh: thing_overlap + ứng viên gán nhãn."""
    name, W, H = job["name"], job["width"], job["height"]
    out = {"name": name, "rules": [], "candidates": [], "error": None}
    try:
        mw, mh, runs, count, mbbox = mask_runs(Path(job["mask"]))
    except Exception as exc:  # mask hỏng: ghi lại, không làm sập cả lô
        out["error"] = f"mask: {exc}"
        return out
    segs = job["segments"]
    if any(s.get("area", 0) > count.get(s["id"], 0) for s in segs):
        out["rules"].append("thing_overlap")
    if job["skip_semantic"]:
        return out
    things = []
    for s in segs:
        if s["thing"] and not s.get("iscrowd") and count.get(s["id"], 0) > 0:
            b = mbbox[s["id"]]
            things.append({"id": s["id"], "cls": s["name"], "area": count[s["id"]], "runs": runs[s["id"]],
                           "bbox": [b[0], b[1], b[2] + 1, b[3] + 1]})
    boxes = [{"i": i, "cls": c, "px": [(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H]}
             for i, (c, x, y, w, h) in enumerate(job["boxes"])]
    pair = {}
    for bi, b in enumerate(boxes):
        for si, s in enumerate(things):
            v = iou(b["px"], s["bbox"])
            if v > 0:
                n_in = inside(s["runs"], b["px"])
                barea = max(1e-9, (b["px"][2] - b["px"][0]) * (b["px"][3] - b["px"][1]))
                pair[bi, si] = {"iou": v, "cov": n_in / s["area"], "fill": n_in / barea}

    def greedy(cond, thr):
        ranked = sorted(((m["iou"], bi, si) for (bi, si), m in pair.items()
                         if cond(boxes[bi], things[si]) and m["iou"] >= thr and bi not in mb and si not in ms), reverse=True)
        found = []
        for _, bi, si in ranked:
            if bi not in mb and si not in ms:
                mb[bi], ms[si] = si, bi
                found.append((bi, si))
        return found

    mb, ms = {}, {}
    same = greedy(lambda b, s: b["cls"] == s["cls"], MATCH_IOU)
    cross = greedy(lambda b, s: b["cls"] != s["cls"], SWAP_IOU)
    img_area = W * H

    def cand(kind, score, b=None, s=None, **ev):
        row = {"image": name, "type": kind, "score": round(score, 4), "evidence": {k: round(v, 4) if isinstance(v, float) else v for k, v in ev.items()}}
        if b is not None:
            row["box"] = {"line": job["lines"][b["i"]], "class": b["cls"], "xyxy": [round(v, 1) for v in b["px"]]}
        if s is not None:
            row["segment"] = {"id": s["id"], "class": s["cls"], "area": s["area"], "xyxy": s["bbox"]}
        out["candidates"].append(row)

    for bi, si in cross:
        m = pair[bi, si]
        cand("class_mismatch", m["iou"], boxes[bi], things[si], iou=m["iou"], cov=m["cov"],
             hypotheses=["class_swap", "category_swap"])
    merged = set()
    for bi, si in same:
        m, s, b = pair[bi, si], things[si], boxes[bi]
        if m["cov"] >= DRIFT_COV:
            continue
        # Pixel tràn khỏi box có rơi vào một box CÙNG LỚP khác không? Có => một segment phủ hai vật (gộp).
        spill = s["area"] - round(m["cov"] * s["area"])
        best = max(((inside(s["runs"], o["px"]) - inside(s["runs"], clip(o["px"], b["px"])), oi)
                    for oi, o in enumerate(boxes) if oi != bi and o["cls"] == s["cls"] and (oi, si) in pair), default=(0, None))
        if best[1] is not None and spill and best[0] / spill >= 0.5 and pair[best[1], si]["fill"] >= MERGE_FILL:
            merged.add(si)
            cand("instance_merge", best[0] / s["area"], b, s, cov=m["cov"], spill_in_other_box=best[0] / spill,
                 other_box_line=job["lines"][boxes[best[1]]["i"]])
        else:
            cand("bbox_drift", 1 - m["cov"], b, s, iou=m["iou"], cov=m["cov"])
    for si, s in enumerate(things):
        if si in ms or s["area"] < MISSING_AREA * img_area:
            continue
        if any(b["cls"] == s["cls"] and pair.get((bi, si), {}).get("iou", 0) >= MATCH_IOU for bi, b in enumerate(boxes)):
            continue  # có box cùng lớp phủ (box trùng tự nhiên của COCO), không phải thiếu
        near = [bi for bi, b in enumerate(boxes) if bi not in mb and b["cls"] == s["cls"] and (bi, si) in pair]
        if near:  # box cùng lớp lệch quá xa nên không ghép được: drift chứ không phải thiếu box
            bi = max(near, key=lambda k: pair[k, si]["iou"])
            mb[bi] = si
            cand("bbox_drift", 1 - pair[bi, si]["cov"], boxes[bi], s, iou=pair[bi, si]["iou"], cov=pair[bi, si]["cov"])
        else:
            cand("missing_box", s["area"] / img_area, None, s, area_ratio=s["area"] / img_area)
    for bi, b in enumerate(boxes):
        if bi in mb:
            continue
        best = max(((pair[bi, si]["fill"], si) for si, s in enumerate(things)
                    if s["cls"] == b["cls"] and si in ms and si not in merged and (bi, si) in pair), default=None)
        if best and best[0] >= MERGE_FILL:
            s = things[best[1]]
            cand("instance_merge", best[0], b, s, fill=best[0], other_box_line=job["lines"][boxes[ms[best[1]]]["i"]])
    return out


def clip(a, b):
    """Giao của hai box [x0,y0,x1,y1] (rỗng thì trả box suy biến)."""
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    return [x0, y0, max(x0, min(a[2], b[2])), max(y0, min(a[3], b[3]))]


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator Day 10 (luật + ứng viên đối chiếu)")
    ap.add_argument("delivery")
    ap.add_argument("--out", required=True, help="errors.json chỉ gồm lỗi luật")
    ap.add_argument("--candidates", help="ứng viên lỗi gán nhãn (cần người xem ảnh)")
    ap.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 2)))
    args = ap.parse_args()
    d = Path(args.delivery)
    man = load_json(d / "manifest.json")["items"]
    meta = {m["image"]: m for m in load_json(d / "metadata.json")["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    names80 = {}
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            k, v = line.split(" ", 1)
            names80[int(k)] = v.strip()
    pan = load_json(d / "panoptic.json")
    cats = {c["id"]: c for c in pan["categories"]}
    img_by_id = {im["id"]: im for im in pan["images"]}
    ann_by_name = {Path(img_by_id[a["image_id"]]["file_name"]).stem: a for a in pan["annotations"] if a["image_id"] in img_by_id}

    errors: set[tuple[str, str]] = set()
    scenes: dict[str, set] = {}
    work = []
    for name in sorted(man):
        it = man[name]
        m = meta.get(name)
        if m:
            scenes.setdefault(m["scene_id"], set()).add(m["split"])
            job = jobs.get(m["job_id"])
            if job and m["guideline_version"] != job["guideline"]:
                errors.add(("guideline_mismatch", name))
        img = d / it["image"]
        if not img.is_file():
            errors.add(("missing_image", name))
        elif sha(img) != it["image_sha256"]:
            errors.add(("wrong_hash", name))
        for key in ("label", "mask"):
            p = d / it[key]
            if p.is_file() and sha(p) != it[f"{key}_sha256"]:
                errors.add(("wrong_hash", name))
        im = img_by_id.get(ann_by_name[name]["image_id"]) if name in ann_by_name else None
        W, H = (im["width"], im["height"]) if im else (1, 1)
        label_path = d / it["label"]
        rows = parse_labels(label_path.read_text(encoding="utf-8")) if label_path.is_file() else []
        valid = []
        for n, c, x, y, w, h in rows:
            if c is None or c not in names80:
                errors.add(("invalid_class", name))
                continue
            tol_x, tol_y = OOB_TOL_PX / W, OOB_TOL_PX / H
            if x - w / 2 < -tol_x or y - h / 2 < -tol_y or x + w / 2 > 1 + tol_x or y + h / 2 > 1 + tol_y:
                errors.add(("bbox_out_of_bounds", name))
            valid.append((n, c, x, y, w, h))
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                a, b = valid[i], valid[j]
                if a[1] == b[1] and abs(a[4] - b[4]) * W <= DUP_SIZE_PX and abs(a[5] - b[5]) * H <= DUP_SIZE_PX \
                        and abs(a[2] - b[2]) * W <= DUP_SHIFT_PX and abs(a[3] - b[3]) * H <= DUP_SHIFT_PX:
                    errors.add(("duplicate_box", name))
        ann = ann_by_name.get(name)
        if ann:
            for s in ann["segments_info"]:
                if s["category_id"] not in cats:
                    errors.add(("invalid_category_id", name))
            mask = d / it["mask"]
            if mask.is_file() and im:
                work.append({
                    "name": name, "width": W, "height": H, "mask": str(mask),
                    "boxes": [(names80[c], x, y, w, h) for _, c, x, y, w, h in valid],
                    "lines": [n for n, *_ in valid],
                    "segments": [{"id": s["id"], "area": s.get("area", 0), "iscrowd": s.get("iscrowd", 0),
                                  "thing": bool(cats.get(s["category_id"], {}).get("isthing")),
                                  "name": cats.get(s["category_id"], {}).get("name")} for s in ann["segments_info"]],
                })
    for sc, splits in scenes.items():
        if len(splits) > 1:
            errors.add(("scene_leak", sc))
    # Mỗi ảnh mang nhiều nhất một lỗi (docs/DELIVERY.md): ảnh đã có lỗi luật thì ứng viên ở đó là nhiễu tự nhiên.
    flagged = {t for _, t in errors}
    for w in work:
        w["skip_semantic"] = w["name"] in flagged
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(analyze, work, chunksize=4))
    cands, failures = [], []
    for r in results:
        for kind in r["rules"]:
            errors.add((kind, r["name"]))
        if r["error"]:
            failures.append({"image": r["name"], "error": r["error"]})
        if r["name"] not in flagged and not r["rules"]:
            cands += r["candidates"]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"errors": [{"type": t, "target": g} for t, g in sorted(errors)]}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(errors)} lỗi luật -> {args.out}")
    if args.candidates:
        cands.sort(key=lambda c: (-c["score"], c["image"], c["type"]))
        doc = {"note": "ứng viên cần người xem ảnh; KHÔNG phải lỗi đã xác nhận", "images": len(man),
               "candidate_images": len({c["image"] for c in cands}), "failures": failures, "candidates": cands}
        Path(args.candidates).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(cands)} ứng viên trên {doc['candidate_images']} ảnh -> {args.candidates}")
    if failures:
        print(f"CẢNH BÁO: {len(failures)} ảnh không đọc được mask", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
