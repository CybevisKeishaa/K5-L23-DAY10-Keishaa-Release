#!/usr/bin/env python3
"""Truy vết ticket của team AI (Pha 5). Chỉ đọc delivery, thư viện chuẩn.

  python validator/trace_query.py <delivery> --out trace.json

tier_a: ảnh trong các cảnh ticket nêu, job theo guideline CŨ (theo jobs.csv, không theo metadata ảnh),
        có >= 1 box detection của lớp bị đổi quy tắc.
tier_b: ảnh khác cùng điều kiện, chưa ai báo.
notify: người gán + người kiểm của các job chứa ảnh tầng a và b.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    d = Path(args.delivery)
    changelog = (d / "guideline" / "changelog.md").read_text(encoding="utf-8")
    ticket = (d / "incoming" / "ticket.md").read_text(encoding="utf-8")
    versions = re.findall(r"^##\s*(v[\d.]+)", changelog, flags=re.M)
    newest = max(versions, key=lambda v: tuple(int(p) for p in v[1:].split(".")))
    m = re.search(r"^##\s*" + re.escape(newest) + r"\s*$(.*?)(?=^##\s|\Z)", changelog, flags=re.M | re.S)
    classes = re.findall(r"`([^`]+)`", m.group(1) if m else "")
    if not classes:
        raise SystemExit("không tìm thấy lớp bị đổi quy tắc trong changelog")
    rule_class = classes[0]
    scenes = set(re.findall(r"scene_\d+", ticket))
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    old_jobs = {j for j, r in jobs.items() if r["guideline"] != newest}
    names = {}
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            k, v = line.split(" ", 1)
            names[k] = v.strip()
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]
    tier_a, tier_b, hit_jobs = [], [], set()
    for row in sorted(meta, key=lambda r: r["image"]):
        if row["job_id"] not in old_jobs:
            continue
        label = d / man[row["image"]]["label"]
        text = label.read_text(encoding="utf-8") if label.is_file() else ""
        if not any(names.get(ln.split()[0]) == rule_class for ln in text.splitlines() if ln.split()):
            continue
        (tier_a if row["scene_id"] in scenes else tier_b).append(row["image"])
        hit_jobs.add(row["job_id"])
    notify = sorted({jobs[j]["annotator"] for j in hit_jobs} | {jobs[j]["reviewer"] for j in hit_jobs})
    Path(args.out).write_text(json.dumps({"tier_a": tier_a, "tier_b": tier_b, "notify": notify}, indent=1) + "\n", encoding="utf-8")
    print(f"lớp={rule_class} guideline mới={newest} job cũ={sorted(old_jobs)} cảnh ticket={sorted(scenes)}")
    print(f"tier_a={len(tier_a)} tier_b={len(tier_b)} notify={notify} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
