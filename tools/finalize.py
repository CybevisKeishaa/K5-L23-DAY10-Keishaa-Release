#!/usr/bin/env python3
"""Chốt bài SAU KHI người đã xem ảnh và lưu review_log.csv. Chạy lại bao nhiêu lần cũng được.

  python tools/finalize.py --run runs/r1119        # seed luyện tập: merge -> v2 -> pack -> lineage -> check -> export
  python tools/finalize.py --de-an delivery        # đề ẩn: merge + trace vào submission/de_an/

Chỉ gọi script gốc trong scripts/ (không sửa chúng).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def py(*args: str, check: bool = True) -> int:
    print("+", " ".join(args), flush=True)
    return subprocess.run([sys.executable, "-X", "utf8", *args], cwd=ROOT, check=check).returncode


def ensure_review_log(path: Path) -> None:
    if not path.is_file():
        path.write_text("image,type,verdict,note\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run")
    g.add_argument("--de-an", dest="de_an")
    args = ap.parse_args()
    if args.de_an:
        out = ROOT / "submission" / "de_an"
        ensure_review_log(out / "review_log.csv")
        py("scripts/merge_review.py", "--rules", str(out / "rules.json"), "--review", str(out / "review_log.csv"), "--out", str(out / "errors.json"))
        py("validator/trace_query.py", args.de_an, "--out", str(out / "trace.json"))
        return 0
    run = ROOT / args.run
    ensure_review_log(run / "review_log.csv")
    py("scripts/merge_review.py", "--rules", str(run / "rules.json"), "--review", str(run / "review_log.csv"), "--out", str(run / "errors.json"))
    rid = json.loads((run / "delivery" / "release.json").read_text(encoding="utf-8"))["release_id"]
    n_err = len({e["target"] for e in json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]})
    decision = "HOLD" if n_err / 250 > 0.02 else "RELEASE"
    lp = run.parent / "lineage.jsonl"
    events = [json.loads(x) for x in lp.read_text(encoding="utf-8").splitlines() if x.strip()] if lp.is_file() else []
    if not any(e.get("event") == "decision" and e.get("release_id") == rid for e in events):
        py("scripts/lineage.py", "record", "--event", "decision", "--release-id", rid, "--decision", decision)
    py("tools/build_v2.py", "--run", str(run))
    py("scripts/pack_release.py", str(run / "handover" / f"{rid}_v2"))
    if not any(e.get("event") == "release" and e.get("release_id") == f"{rid}_v2" for e in events):
        py("scripts/lineage.py", "record", "--event", "release", "--release-id", f"{rid}_v2", "--parent", rid)
    py("scripts/lineage.py", "impact", "--release-id", rid)
    code = py("scripts/check_handover.py", "--run", str(run), check=False)
    py("scripts/export_submission.py", "--run", str(run))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
