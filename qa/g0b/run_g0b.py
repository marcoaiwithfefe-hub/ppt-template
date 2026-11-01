"""Gate G0b (rev 8, map rev 5): the eight sample-design templates filled with fixtures/reference-outline.md on the route
D11 picks, rendered with headless LibreOffice (qa/g0b/lo_render.py, render-only font copy), one contact sheet each.

Script half of the gate, per template: the route and picks, each output slide's flags, the warnings, and every pair
of text boxes holding text whose slide-space boxes overlap on the output but not on the sample they were copied from.
The eye half (decoration on every slide, no text past a box unless the slide is warned or check-this-slide) is read off
the sheets and written into qa/g0b/G0B-RESULT.md.

    .venv/bin/python qa/g0b/run_g0b.py [--before]     (--before also renders Marco's template on the layout route)
"""
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from lxml import etree  # noqa: E402

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402
from deckfill.sample import has_text, shape_id, to_slide, walk, _local_box  # noqa: E402
from deckfill.xmlsafe import q  # noqa: E402

SET = [
    "corporate-sales-pitch-slides-2.pptx", "elegant-pitch-deck.pptx", "3d-modern-background-pitch-deck.pptx",
    "business-conference-slides.pptx", "simple-business-proposal-slides.pptx", "viola-free-presentation-template.pptx",
    "bullen-free-presentation-template.pptx", "marco-year-in-breakdowns.pptx",
]
OUT = ROOT / "qa" / "g0b"
OUTLINE = (ROOT / "fixtures" / "reference-outline.md").read_text(encoding="utf-8")


def text_boxes(xml: bytes) -> dict[int, tuple]:
    root = etree.fromstring(xml)
    tree = root.find(q("p:cSld")).find(q("p:spTree"))
    out = {}
    for w in walk(tree):
        if etree.QName(w.el).localname != "sp" or not has_text(w.el) or w.hidden:
            continue
        box = _local_box(w.el)
        if box is not None and shape_id(w.el) is not None:
            out[shape_id(w.el)] = to_slide(box, w.chain)
    return out


def overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def slide_xml(parts: dict, n: int) -> bytes:
    return parts[f"ppt/slides/slide{n}.xml"]


def run(name: str, route: str | None, tag: str) -> dict:
    data = (ROOT / "qa" / "real-templates" / name).read_bytes()
    t0 = time.time()
    info = read_template(data, name)
    route = route or info.route
    plan = plan_deck(info, parse_outline(OUTLINE), None, route=route)
    deck = fill(data, name, plan)
    secs = round(time.time() - t0, 2)
    d = OUT / tag
    d.mkdir(parents=True, exist_ok=True)
    out_pptx = d / f"{tag}-filled.pptx"
    out_pptx.write_bytes(deck)
    rep = {"template": name, "route": route, "routes": list(info.routes), "default_route": info.route, "seconds": secs,
           "samples": [{"id": s.id, "usable": s.usable, "reason": s.reason, "design": s.design, "classes": list(s.classes)} for s in info.samples],
           "chosen": list(plan.chosen), "warnings": [[w.code, w.text] for w in plan.warnings], "slides": [], "new_overlaps": []}
    if route == "sample":
        with zipfile.ZipFile(io.BytesIO(deck)) as z:
            parts = {n: z.read(n) for n in z.namelist()}
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            src = {n: z.read(n) for n in z.namelist()}
        samples = {s.id: s for s in info.samples}
        for i, ps in enumerate(plan.slides, start=1):
            S = samples[ps.layout]
            rep["slides"].append({"n": i, "sample": ps.layout, "title": ps.title, "flags": list(ps.flags)})
            out_boxes = text_boxes(slide_xml(parts, i))
            in_boxes = text_boxes(src[S.part.lstrip("/")])
            ids = sorted(out_boxes)
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    x, y = ids[a], ids[b]
                    if overlaps(out_boxes[x], out_boxes[y]):
                        before = x in in_boxes and y in in_boxes and overlaps(in_boxes[x], in_boxes[y])
                        if not before:
                            rep["new_overlaps"].append({"slide": i, "boxes": [x, y], "flags": list(ps.flags)})
    else:
        rep["slides"] = [{"n": i, "layout": ps.layout, "title": ps.title, "fit": ps.fit} for i, ps in enumerate(plan.slides, start=1)]
    subprocess.run([sys.executable, str(OUT / "lo_render.py"), str(out_pptx), str(d / "renders"), "36"], check=True, capture_output=True, timeout=900)
    pngs = sorted((d / "renders").glob("slide-*.png"))
    cols = 4
    rows = -(-len(pngs) // cols)
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-y", "-pattern_type", "glob", "-i", str(d / "renders" / "slide-*.png"),
                    "-vf", f"scale=480:-2,tile={cols}x{rows}:padding=6:color=white", "-frames:v", "1", "-q:v", "4", str(d / "sheet.jpg")], check=True)
    rep["sheet"] = str((d / "sheet.jpg").relative_to(ROOT))
    rep["renders"] = str((d / "renders").relative_to(ROOT))
    (d / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


if __name__ == "__main__":
    reports = []
    for name in SET:
        r = run(name, None, Path(name).stem)
        reports.append({k: r[k] for k in ("template", "route", "default_route", "seconds", "chosen", "new_overlaps", "sheet")})
        print(name, r["route"], r["seconds"], "s", len(r["slides"]), "slides", "overlaps", len(r["new_overlaps"]), flush=True)
    if "--before" in sys.argv:
        r = run("marco-year-in-breakdowns.pptx", "layout", "marco-before-layout-route")
        print("before (layout route)", r["sheet"])
    (OUT / "g0b-runs.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1))
