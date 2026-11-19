#!/usr/bin/env python3
"""Công cụ xem ảnh cho Pha 2 (được dùng Pillow; validator thì không).

  python tools/review_tool.py <delivery> --candidates <candidates.json> --out <thư_mục_review>

Sinh mỗi ảnh ứng viên một PNG: [ảnh gốc | box detection + viền segment panoptic], và review.html
để NGƯỜI xem ảnh chọn confirmed/rejected, ghi thấy gì, rồi bấm "Tải review_log.csv".
Công cụ không tự điền kết luận nào.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402

SEMANTIC = ["class_swap", "category_swap", "bbox_drift", "missing_box", "instance_merge"]


def seg_mask(mask_path: Path, sid: int) -> Image.Image:
    w, h, px = pngutil.read_rgb(mask_path)
    m = bytearray(w * h)
    for p in range(w * h):
        i = 3 * p
        if px[i] | px[i + 1] << 8 | px[i + 2] << 16 == sid:
            m[p] = 255
    return Image.frombytes("L", (w, h), bytes(m))


def render(d: Path, man: dict, name: str, cands: list, out: Path, names80: dict) -> None:
    it = man[name]
    img_path = d / it["image"]
    base = Image.open(img_path).convert("RGB") if img_path.is_file() else Image.new("RGB", (640, 480), "gray")
    W, H = base.size
    over = base.copy()
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for sid in {c["segment"]["id"] for c in cands if "segment" in c}:
        m = seg_mask(d / it["mask"], sid)
        ld.bitmap((0, 0), m, fill=(0, 255, 0, 90))
        edge = m.filter(ImageFilter.FIND_EDGES)
        ld.bitmap((0, 0), edge, fill=(0, 255, 0, 255))
    over = Image.alpha_composite(over.convert("RGBA"), layer).convert("RGB")
    dr = ImageDraw.Draw(over)
    label = (d / it["label"]).read_text(encoding="utf-8").splitlines()
    hot = {c["box"]["line"] for c in cands if "box" in c}
    for n, ln in enumerate(label, 1):
        p = ln.split()
        if len(p) < 5:
            continue
        x, y, w, h = map(float, p[1:5])
        xy = [(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H]
        col, wd = ("red", 3) if n in hot else ((80, 160, 255), 1)
        dr.rectangle(xy, outline=col, width=wd)
        dr.text((xy[0] + 3, xy[1] + 2), names80.get(p[0], p[0]), fill=col)
    for c in cands:
        if "segment" in c:
            x0, y0, _, _ = c["segment"]["xyxy"]
            dr.text((x0 + 3, max(0, y0 - 12)), f"seg:{c['segment']['class']}", fill=(0, 255, 0))
    scale = 2 if W < 400 else 1
    sheet = Image.new("RGB", (2 * W * scale + 10, H * scale), "white")
    sheet.paste(base.resize((W * scale, H * scale)), (0, 0))
    sheet.paste(over.resize((W * scale, H * scale)), (W * scale + 10, 0))
    sheet.save(out / f"{name}.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    d, out = Path(args.delivery), Path(args.out)
    (out / "img").mkdir(parents=True, exist_ok=True)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    names80 = dict(ln.split(" ", 1) for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip())
    names80 = {k: v.strip() for k, v in names80.items()}
    cands = json.loads(Path(args.candidates).read_text(encoding="utf-8"))["candidates"]
    by_img: dict[str, list] = {}
    for c in cands:
        by_img.setdefault(c["image"], []).append(c)
    order = sorted(by_img, key=lambda n: -max(c["score"] for c in by_img[n]))
    cards = []
    for k, name in enumerate(order, 1):
        render(d, man, name, by_img[name], out / "img", names80)
        lines = []
        for c in by_img[name]:
            b = f"box dòng {c['box']['line']} = <b>{html.escape(c['box']['class'])}</b>" if "box" in c else "không có box"
            s = f"segment = <b>{html.escape(c['segment']['class'])}</b> ({c['segment']['area']} px)" if "segment" in c else ""
            lines.append(f"<li><code>{c['type']}</code> score={c['score']} · {b} · {s} · {html.escape(json.dumps(c['evidence'], ensure_ascii=False))}</li>")
        opts = "".join(f'<option value="{t}">{t}</option>' for t in SEMANTIC)
        cards.append(f"""<section data-img="{name}"><h3>{k}. {name}</h3>
<img src="img/{name}.png" loading="lazy"><ul>{''.join(lines)}</ul>
<label>Loại <select class="t"><option value=""></option>{opts}</select></label>
<label><input type="radio" name="v_{name}" value="confirmed"> confirmed</label>
<label><input type="radio" name="v_{name}" value="rejected"> rejected</label>
<label><input type="radio" name="v_{name}" value="" checked> chưa xem</label><br>
<textarea class="n" rows="2" placeholder="Thấy gì trong ảnh (>= 20 ký tự), ví dụ: xe tải mui kín, detection ghi car"></textarea>
</section>""")
    page = f"""<!doctype html><meta charset="utf-8"><title>Review {html.escape(str(d))}</title>
<style>body{{font:14px sans-serif;margin:16px;max-width:1400px}}section{{border-top:2px solid #ccc;padding:8px 0}}
img{{max-width:100%}}textarea{{width:100%}}#bar{{position:sticky;top:0;background:#fff;padding:6px;border-bottom:1px solid #999}}</style>
<div id="bar">{len(order)} ảnh ứng viên. Đỏ = box bị nghi; xanh dương = box khác; xanh lá = segment bị nghi.
Mỗi ảnh nhiều nhất một lỗi. <b>Người</b> xem ảnh rồi chọn. Tự lưu trong trình duyệt.
<button onclick="dl()">Tải review_log.csv</button> <span id="st"></span></div>
{''.join(cards)}
<script>
const K='review:'+location.pathname;
function rows(){{return [...document.querySelectorAll('section')].map(s=>({{img:s.dataset.img,t:s.querySelector('.t').value,
v:(s.querySelector('input:checked')||{{}}).value||'',n:s.querySelector('.n').value.trim()}}))}}
function save(){{try{{localStorage.setItem(K,JSON.stringify(rows()))}}catch(e){{}}
const r=rows();document.getElementById('st').textContent=r.filter(x=>x.v).length+'/'+r.length+' đã quyết định'}}
try{{(JSON.parse(localStorage.getItem(K))||[]).forEach(x=>{{const s=document.querySelector(`section[data-img="${{x.img}}"]`);if(!s)return;
s.querySelector('.t').value=x.t;s.querySelector('.n').value=x.n;const r=s.querySelector(`input[value="${{x.v}}"]`);if(r)r.checked=true}})}}catch(e){{}}
document.addEventListener('input',save);document.addEventListener('change',save);save();
function q(x){{return '"'+x.replace(/"/g,'""')+'"'}}
function dl(){{const bad=rows().filter(x=>x.v&&(!x.t||x.n.length<20));if(bad.length){{alert('Thiếu loại hoặc ghi chú < 20 ký tự: '+bad.map(x=>x.img).join(', '));return}}
const csv='image,type,verdict,note\\n'+rows().filter(x=>x.v).map(x=>[x.img,x.t,x.v,q(x.n)].join(',')).join('\\n')+'\\n';
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='review_log.csv';a.click()}}
</script>"""
    (out / "review.html").write_text(page, encoding="utf-8")
    print(f"{len(order)} ảnh -> {out / 'review.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
