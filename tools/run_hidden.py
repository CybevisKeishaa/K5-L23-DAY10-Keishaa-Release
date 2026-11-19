#!/usr/bin/env python3
"""Đề ẩn: giải nén an toàn, chạy validator + truy vết + công cụ review cho mọi delivery tìm thấy.

  python tools/run_hidden.py <de_an.zip | thư_mục> [--assign <mã_đề>]

- Giải nén vào runs/day10_hidden/<tên zip>/ (không ghi đè zip gốc), chặn path traversal,
  BỎ QUA mọi thứ trong _private/ (không giải nén, không đọc).
- Mỗi delivery (thư mục có manifest.json) chạy riêng; một đề lỗi không làm sập cả lô.
- --assign <mã_đề>: chép rules/candidates/trace của đề được giao vào submission/de_an/ và mở hàng đợi review.
  Sau khi NGƯỜI xem ảnh và lưu submission/de_an/review_log.csv: python tools/finalize.py --de-an <delivery>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def py(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def safe_extract(zpath: Path, dest: Path) -> list[str]:
    skipped = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            parts = Path(info.filename.replace("\\", "/")).parts
            target = (dest / info.filename).resolve()
            if "_private" in parts or "__MACOSX" in parts or not target.is_relative_to(dest.resolve()):
                skipped.append(info.filename)
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            if info.filename.lower().endswith(".zip"):  # zip lồng (mỗi mã đề một zip)
                skipped += safe_extract(target, target.with_suffix(""))
    return skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--assign", help="mã đề được giao (tên thư mục chứa delivery)")
    args = ap.parse_args()
    src = Path(args.source)
    base = ROOT / "runs" / "day10_hidden" / src.stem
    base.mkdir(parents=True, exist_ok=True)
    inventory = {"source": str(src)}
    if src.is_file():
        inventory["sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
        inventory["skipped"] = safe_extract(src, base / "extracted")
        root = base / "extracted"
    else:
        root = src
    deliveries = sorted(p.parent for p in root.rglob("manifest.json") if "_private" not in p.parts)
    rows = []
    for d in deliveries:
        exam = d.parent.name if d.name == "delivery" else d.name
        out = base / exam
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        a = py("validator/validate.py", str(d), "--out", str(out / "rules.json"), "--candidates", str(out / "candidates.json"))
        b = py("validator/trace_query.py", str(d), "--out", str(out / "trace.json"))
        c = py("tools/review_tool.py", str(d), "--candidates", str(out / "candidates.json"), "--out", str(out / "review"))
        ok = a.returncode == b.returncode == c.returncode == 0
        row = {"exam": exam, "delivery": str(d), "status": "OK" if ok else "FAIL", "seconds": round(time.time() - t0, 1)}
        if ok:
            man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
            cands = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
            row.update(images=len(man), rule_errors=len(json.loads((out / "rules.json").read_text(encoding="utf-8"))["errors"]),
                       candidates=len(cands["candidates"]), review_images=cands["candidate_images"])
        else:
            row["error"] = (a.stderr + b.stderr + c.stderr)[-500:]
        rows.append(row)
        print(row, flush=True)
    inventory["exams"] = rows
    (base / "inventory.json").write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    with (base / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["exam", "images", "rule_errors", "candidates", "review_images", "seconds", "status", "delivery", "error"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} đề -> {base / 'summary.csv'}")
    if args.assign:
        row = next((r for r in rows if r["exam"] == args.assign and r["status"] == "OK"), None)
        if not row:
            raise SystemExit(f"không có đề {args.assign} chạy OK")
        sub = ROOT / "submission" / "de_an"
        sub.mkdir(parents=True, exist_ok=True)
        for name in ("rules.json", "candidates.json", "trace.json"):
            shutil.copyfile(base / args.assign / name, sub / name)
        shutil.copyfile(base / args.assign / "rules.json", sub / "errors.json")  # tạm: chỉ lỗi luật, chốt lại sau review
        print(f"đề {args.assign}: mở {base / args.assign / 'review' / 'review.html'}, xem {row['review_images']} ảnh, "
              f"lưu review_log.csv vào {sub}, rồi: python tools/finalize.py --de-an \"{row['delivery']}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
