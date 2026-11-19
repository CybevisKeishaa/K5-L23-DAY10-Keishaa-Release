"""Kiểm validator trên fixture TỰ gài vào bản sao lô sạch (không đọc _private).

  python scripts/inject_release.py --seed 5 --no-faults --out runs/clean
  python -m unittest tests.test_validator -v
"""
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "runs" / "clean" / "delivery"
sys.path.insert(0, str(ROOT / "scripts"))
import pngutil  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate(d: Path, tmp: Path):
    subprocess.run([sys.executable, str(ROOT / "validator" / "validate.py"), str(d), "--out", str(tmp / "e.json"),
                    "--candidates", str(tmp / "c.json")], check=True, capture_output=True)
    errs = {(e["type"], e["target"]) for e in json.loads((tmp / "e.json").read_text(encoding="utf-8"))["errors"]}
    cands = {(c["type"], c["image"]) for c in json.loads((tmp / "c.json").read_text(encoding="utf-8"))["candidates"]}
    return errs, cands


@unittest.skipUnless((CLEAN / "manifest.json").is_file(), "chưa có runs/clean")
class ValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.clean = validate(CLEAN, cls.tmp)
        d = cls.d = cls.tmp / "delivery"
        shutil.copytree(CLEAN, d)
        man_doc = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        man = man_doc["items"]
        meta_doc = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
        cats = {c["id"]: c for c in pan["categories"]}
        anns = {Path(a["file_name"]).stem: a for a in pan["annotations"]}
        names = sorted(man)
        jobs = {r["job_id"]: r for r in csv.DictReader((d / "jobs.csv").open(encoding="utf-8"))}

        def labels(n):
            return [ln.split() for ln in (d / man[n]["label"]).read_text(encoding="utf-8").splitlines() if ln.strip()]

        def put(n, rows):
            (d / man[n]["label"]).write_text("".join(" ".join(r) + "\n" for r in rows), encoding="utf-8")
            man[n]["label_sha256"] = sha(d / man[n]["label"])

        free = iter(names)
        cls.expect_rules, cls.expect_cands = set(), set()
        # --- ứng viên: missing_box (bỏ box lớn nhất), bbox_drift (dịch 25%), class_mismatch (đổi lớp)
        for n in free:
            rows = labels(n)
            if len(rows) >= 2:
                big = max(rows, key=lambda r: float(r[3]) * float(r[4]))
                if float(big[3]) * float(big[4]) > 0.05 and sum(r[0] == big[0] for r in rows) == 1:
                    rows.remove(big)
                    put(n, rows)
                    cls.expect_cands.add(("missing_box", n))
                    break
        for n in free:
            rows = labels(n)
            big = max(rows, key=lambda r: float(r[3]) * float(r[4]))
            if 0.05 < float(big[3]) * float(big[4]) < 0.5 and float(big[1]) < 0.6:
                big[1] = f"{float(big[1]) + 0.25 * float(big[3]):.6f}"
                put(n, rows)
                cls.expect_cands.add(("bbox_drift", n))
                break
        for n in free:
            rows = labels(n)
            big = max(rows, key=lambda r: float(r[3]) * float(r[4]))
            if float(big[3]) * float(big[4]) > 0.05:
                big[0] = str((int(big[0]) + 1) % 80)
                put(n, rows)
                cls.expect_cands.add(("class_mismatch", n))
                break
        # --- instance_merge: gộp hai segment thing cùng lớp
        for n in free:
            segs = [s for s in anns[n]["segments_info"] if cats[s["category_id"]]["isthing"] and not s.get("iscrowd")]
            by = {}
            for s in segs:
                by.setdefault(s["category_id"], []).append(s)
            pair = next((sorted(v, key=lambda s: s["area"]) for v in by.values() if len(v) >= 2 and min(s["area"] for s in v) > 2000), None)
            if not pair:
                continue
            gone, kept = pair[0], pair[-1]
            w, h, px = pngutil.read_rgb(d / man[n]["mask"])
            rgb = bytes(pngutil.segment_rgb(kept["id"]))
            for i in range(0, len(px), 3):
                if pngutil.segment_id(px, i) == gone["id"]:
                    px[i:i + 3] = rgb
            pngutil.write_rgb(d / man[n]["mask"], w, h, bytes(px))
            kept["area"] += gone["area"]
            anns[n]["segments_info"].remove(gone)
            man[n]["mask_sha256"] = sha(d / man[n]["mask"])
            cls.expect_cands.add(("instance_merge", n))
            break
        # --- lỗi luật
        n = next(free); put(n, labels(n) + [["80", "0.5", "0.5", "0.1", "0.1"]]); cls.expect_rules.add(("invalid_class", n))
        n = next(free); put(n, labels(n) + [["0", "0.97", "0.5", "0.1", "0.1"]]); cls.expect_rules.add(("bbox_out_of_bounds", n))
        n = next(free); r = labels(n); dup = list(r[0]); dup[1] = f"{float(dup[1]) + 1.5 / 640:.6f}"; put(n, r + [dup])
        cls.expect_rules.add(("duplicate_box", n))
        n = next(free); (d / man[n]["image"]).unlink(); cls.expect_rules.add(("missing_image", n))
        n = next(free); man[n]["image_sha256"] = "0" * 64; cls.expect_rules.add(("wrong_hash", n))
        n = next(free); anns[n]["segments_info"][0]["category_id"] = 254; cls.expect_rules.add(("invalid_category_id", n))
        n = next(free); anns[n]["segments_info"][0]["area"] += 50; cls.expect_rules.add(("thing_overlap", n))
        n = next(free)
        m = next(x for x in meta_doc["items"] if x["image"] == n)
        m["guideline_version"] = "v1.2" if jobs[m["job_id"]]["guideline"] == "v1.3" else "v1.3"
        cls.expect_rules.add(("guideline_mismatch", n))
        n = next(free)
        m = next(x for x in meta_doc["items"] if x["image"] == n)
        m["split"] = "val" if m["split"] == "train" else "train"
        cls.expect_rules.add(("scene_leak", m["scene_id"]))
        (d / "manifest.json").write_text(json.dumps(man_doc), encoding="utf-8")
        (d / "metadata.json").write_text(json.dumps(meta_doc), encoding="utf-8")
        (d / "panoptic.json").write_text(json.dumps(pan), encoding="utf-8")
        cls.got = validate(d, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_clean_batch_is_silent(self):
        self.assertEqual(self.clean, (set(), set()))

    def test_all_nine_rules(self):
        self.assertEqual(len({t for t, _ in self.expect_rules}), 9)
        self.assertEqual(self.got[0], self.expect_rules)

    def test_semantic_candidates(self):
        self.assertEqual(len(self.expect_cands), 4)
        self.assertLessEqual(self.expect_cands, self.got[1])
        self.assertLessEqual(len(self.got[1] - self.expect_cands), 1)  # ít báo thừa

    def test_deterministic(self):
        self.assertEqual(validate(self.d, self.tmp), self.got)


if __name__ == "__main__":
    unittest.main()
