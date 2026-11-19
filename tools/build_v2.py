#!/usr/bin/env python3
"""Pha 4: dựng lô v2 từ delivery v1 + errors.json, KHÔNG sửa delivery/.

  python tools/build_v2.py --run runs/r<seed>
  python scripts/pack_release.py runs/r<seed>/handover/<release_id>_v2

- Lỗi nhãn detection / thiếu file -> rework_queue.csv, ảnh rời v2.
- wrong_hash: mở ảnh kiểm (Pillow decode + đúng kích thước panoptic); còn nguyên thì giữ, hash mới vào manifest.csv; hỏng thì rework.
- guideline_mismatch: truyvet.csv ghi guideline theo job. scene_leak: cả cảnh về split đa số.
- Lỗi chỉ ở panoptic: ảnh ở lại v2, ghi vào README Ghi chú.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image

DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box", "class_swap", "bbox_drift", "missing_box"}
PANOPTIC = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
ACTION = {
    "missing_image": "thiếu file ảnh: lấy lại ảnh gốc rồi gán lại",
    "invalid_class": "class_id ngoài 0-79: gán lại lớp",
    "bbox_out_of_bounds": "box tràn mép ảnh: kẻ lại box",
    "duplicate_box": "box bị lặp: xoá box thừa",
    "class_swap": "box gán nhầm lớp: sửa lớp",
    "bbox_drift": "box lệch khỏi vật: kẻ lại box",
    "missing_box": "thiếu box cho vật: thêm box",
    "wrong_hash": "ảnh hỏng (không mở được): lấy lại ảnh gốc",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = Path(args.run)
    d = run / "delivery"
    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    names80 = {}
    for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            k, v = ln.split(" ", 1)
            names80[int(k)] = v.strip()
    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    size = {Path(im["file_name"]).stem: (im["width"], im["height"]) for im in pan["images"]}
    errors = json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]
    by_img = {e["target"]: e["type"] for e in errors if e["target"] in man}
    leaks = {e["target"] for e in errors if e["type"] == "scene_leak"}

    rework, hash_notes = {}, []
    for name, kind in sorted(by_img.items()):
        if kind in DET_REWORK:
            rework[name] = kind
        elif kind == "wrong_hash":
            try:
                with Image.open(d / man[name]["image"]) as im:
                    im.load()
                    ok = im.size == size.get(name)
            except Exception:
                ok = False
            if ok:
                hash_notes.append(name)
            else:
                rework[name] = "wrong_hash"

    v2 = run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()
    keep = [n for n in sorted(man) if n not in rework and (d / man[n]["image"]).is_file()]
    for n in keep:
        shutil.copyfile(d / man[n]["image"], v2 / "images" / f"{n}.jpg")
        shutil.copyfile(d / man[n]["label"], v2 / "labels" / f"{n}.txt")

    with (v2 / "rework_queue.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "type", "annotator", "reviewer", "action"])
        for n, kind in sorted(rework.items()):
            job = jobs[meta[n]["job_id"]]
            w.writerow([n, kind, job["annotator"], job["reviewer"], ACTION[kind]])

    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir())
    with (v2 / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "sha256"])
        for p in files:
            w.writerow([p.relative_to(v2).as_posix(), sha(p)])

    counts = Counter()
    for n in keep:
        for ln in (v2 / "labels" / f"{n}.txt").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                counts[names80[int(float(ln.split()[0]))]] += 1
    with (v2 / "label_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["class", "count"])
        for cls in sorted(counts):
            w.writerow([cls, counts[cls]])
        w.writerow(["TOTAL", sum(counts.values())])

    # scene_leak: đưa cả cảnh về split đa số của cảnh đó
    scene_split = {}
    for sc in {m["scene_id"] for m in meta.values()}:
        splits = Counter(m["split"] for m in meta.values() if m["scene_id"] == sc)
        scene_split[sc] = splits.most_common(1)[0][0]
    with (v2 / "truyvet.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"])
        for n in keep:
            m, job = meta[n], jobs[meta[n]["job_id"]]
            w.writerow([n, m["scene_id"], scene_split[m["scene_id"]], m["job_id"], job["annotator"], job["reviewer"], job["guideline"]])

    n_err = len({e["target"] for e in errors})
    rate = n_err / len(man)
    by_ver = {}
    for j in sorted(jobs):
        by_ver.setdefault(jobs[j]["guideline"], []).append(j)
    gl = ", ".join(f"{v} ({js[0]}-{js[-1]})" for v, js in sorted(by_ver.items()))
    pan_imgs = sorted(n for n, k in by_img.items() if k in PANOPTIC)
    gm = sorted(n for n, k in by_img.items() if k == "guideline_mismatch")
    owners = Counter(jobs[meta[n]["job_id"]]["annotator"] for n in rework)
    v1_decision = "Hold" if rate > 0.02 else "Release"
    notes = [
        f"scene_leak {', '.join(sorted(leaks)) or '(không có)'}: cả cảnh đưa về một split (split đa số của cảnh) trong truyvet.csv.",
        f"wrong_hash {', '.join(hash_notes) or '(không có)'}: đã mở ảnh (giải mã được, đúng kích thước), chỉ manifest v1 sai, manifest.csv v2 ghi hash mới.",
        f"guideline_mismatch {', '.join(gm) or '(không có)'}: truyvet.csv ghi guideline theo job trong jobs.csv.",
        f"Rework {len(rework)} ảnh giao lại đúng người gán/kiểm của job ({', '.join(f'{a}: {c}' for a, c in sorted(owners.items())) or 'không có'}).",
        f"Lỗi chỉ ở panoptic (ảnh ở lại v2, báo team panoptic): {', '.join(pan_imgs) or '(không có)'}.",
    ]
    readme = "\n".join([
        f"Release: {rid}_v2",
        f"Parent: {rid}",
        f"Số ảnh: {len(keep)}",
        f"Số nhãn: {sum(counts.values())}",
        f"Guideline: {gl}",
        f"QC v1: {n_err}/{len(man)} = {rate * 100:.1f}%".replace(".", ","),
        f"Kết luận v1: {v1_decision} — {n_err}/{len(man)} = {rate * 100:.1f}% {'vượt' if rate > 0.02 else 'không vượt'} ngưỡng 2%",
        f"Kết luận v2: Release — tách {len(rework)} ảnh lỗi nhãn detection sang rework, sửa split/hash/guideline; còn {len(pan_imgs)} ảnh lỗi panoptic ở lại (nhãn detection đúng)",
        "Ghi chú: " + " ".join(notes),
        "",
    ])
    (v2 / "README.txt").write_text(readme, encoding="utf-8")
    print(f"v2: {len(keep)} ảnh, {sum(counts.values())} nhãn, rework {len(rework)} -> {v2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
