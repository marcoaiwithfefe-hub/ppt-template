"""Gate G0: fill real public templates with fixtures/reference-outline.md and judge clean fills.

Run: .venv/bin/python qa/g0/run_g0.py [template ...]
Defaults to every .pptx/.potx under qa/real-templates/. Writes outputs, per-slide renders
(macOS Quick Look) and a contact sheet per template under qa/g0/<name>/, and qa/g0/report.json.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from oracle import kept_part_problems, new_parts, parts_of, read_deck  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from pptx import Presentation  # noqa: E402

from deckfill import DeckfillError, fill, parse_outline, plan_deck, read_template  # noqa: E402
from deckfill.package import check_integrity  # noqa: E402

sys.path.insert(0, str(ROOT / "qa"))
from provenance import tested  # noqa: E402

OUT = ROOT / "qa" / "g0"
REAL = ROOT / "qa" / "real-templates"
SUFFIXES = ("（續）", " (cont.)")


def expected_sequence(outline):
    """What the outline says, in order, as (text, level); titles and subtitles are level 0."""
    seq = []
    for s in outline.slides:
        seq.append((s.title, 0))
        seq.extend((t, "sub") for t in s.subtitle)
        for col in s.columns:
            seq.extend((it.text, it.level) for it in col)
    return seq


def actual_sequence(deck):
    """What the deck holds, in reading order, continuation titles folded back; a subtitle placed in
    a body (D3 fallback) reads as level 0 when it follows a title slide's title."""
    seq = []
    prev_title = None
    for s in deck:
        title = s.title or ""
        cont = any(title.endswith(x) and title[: -len(x)] == prev_title for x in SUFFIXES)
        if not cont:
            seq.append((title, 0))
            prev_title = title
        seq.extend((t, 0) for t in s.subtitle if t)
        cols = s.bodies
        if cont:
            # continuation slides carry the rest of each column; fold them back in column order
            pass
        for col in cols:
            seq.extend((text, lvl) for lvl, text in col)
    return seq


def same_sequence(expected, actual):
    """Exact order and text. A subtitle line ("sub") matches level 0 in a subtitle placeholder or
    level 1 as the first paragraphs of a body (D3 step 4 fallback when no title layout fits)."""
    return len(expected) == len(actual) and all(
        et == at and (el == al or (el == "sub" and al in (0, 1)))
        for (et, el), (at, al) in zip(expected, actual)
    )


def render_slides(pptx_path: Path, outdir: Path) -> list[Path]:
    """One-slide copies rendered with macOS Quick Look, the way the spike did."""
    outdir.mkdir(parents=True, exist_ok=True)
    n = len(Presentation(pptx_path).slides)
    pngs = []
    for i in range(n):
        p = Presentation(pptx_path)
        ids = p.slides._sldIdLst
        for j, sid in reversed(list(enumerate(list(ids)))):
            if j != i:
                ids.remove(sid)
        one = outdir / f"slide{i + 1:02d}.pptx"
        p.save(one)
        subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", str(outdir), str(one)], capture_output=True, timeout=120)
        png = outdir / f"slide{i + 1:02d}.pptx.png"
        if png.exists():
            pngs.append(png)
    return pngs


def contact_sheet(pngs: list[Path], dest: Path, label: str) -> None:
    if not pngs:
        return
    thumbs = [Image.open(p).convert("RGB") for p in pngs]
    w = 520
    thumbs = [t.resize((w, int(t.height * w / t.width))) for t in thumbs]
    h = max(t.height for t in thumbs)
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 16) + 16, rows * (h + 40) + 56), "white")
    d = ImageDraw.Draw(sheet)
    d.text((16, 16), label, fill="black")
    for k, t in enumerate(thumbs):
        x, y = 16 + (k % cols) * (w + 16), 48 + (k // cols) * (h + 40)
        sheet.paste(t, (x, y))
        d.rectangle([x - 1, y - 1, x + t.width, y + t.height], outline="#999")
        d.text((x, y + t.height + 6), f"slide {k + 1}", fill="black")
    sheet.save(dest)


def run_one(path: Path, outline_text: str) -> dict:
    name = path.stem
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    rec: dict = {"template": path.name, "bytes": len(data)}
    t = time.time()
    try:
        info = read_template(data, path.name)
    except DeckfillError as e:
        rec.update(result="refused", code=e.code, detail=e.detail)
        return rec
    outline = parse_outline(outline_text)
    plan = plan_deck(info, outline, route="layout")  # G0 is the layout route's gate (rev 8: some now default to sample)
    out = fill(data, path.name, plan)
    rec["seconds"] = round(time.time() - t, 2)
    out_path = work / f"{name}-filled.pptx"
    out_path.write_bytes(out)
    rec["layouts"] = [
        {"name": lay.name, "master": lay.master, "class": lay.cls, "bodies": len(lay.bodies),
         "unmodelled": [b.why_unmodelled for b in lay.bodies if b.fit is None]}
        for lay in info.layouts
    ]
    names = {lay.id: f"{lay.name} [{lay.cls}]" for lay in info.layouts}
    rec["defaults"] = {k: (names[v] if v else None) for k, v in info.defaults}
    rec["picks"] = [f"{s.title} -> {names[s.layout]} ({s.fit})" for s in plan.slides]
    rec["warnings"] = [f"{w.line} {w.code}" for w in plan.warnings]
    deck = read_deck(out)
    rec["c1_round_trip"] = same_sequence(expected_sequence(outline), actual_sequence(deck))
    rec["c3_kept_problems"] = kept_part_problems(data, out)
    rec["c3_unexpected_new_parts"] = [n for n in new_parts(data, out) if not n.startswith("ppt/slides/")]
    rec["c5_integrity"] = check_integrity(parts_of(out))
    rec["c6_empty_placeholders"] = [
        (s.n, ptype, idx) for s in deck for ptype, idx, has in s.placeholders
        if not has and ptype not in ("sldNum", "ftr", "dt")
    ]
    rec["text_outside_placeholders"] = [(s.n, s.loose_text) for s in deck if s.loose_text]  # F12
    pngs = render_slides(out_path, work / "renders")
    rec["renders"] = [str(p.relative_to(ROOT)) for p in pngs]
    sheet = work / f"{name}-sheet.png"
    contact_sheet(pngs, sheet, f"{path.name}: {len(pngs)} slides")
    rec["sheet"] = str(sheet.relative_to(ROOT))
    rec["script_clean"] = (
        rec["c1_round_trip"] and not rec["c3_kept_problems"] and not rec["c3_unexpected_new_parts"]
        and not rec["c5_integrity"] and not rec["c6_empty_placeholders"] and not rec["text_outside_placeholders"]
    )
    return rec


def main() -> None:
    outline_text = (ROOT / "fixtures" / "reference-outline.md").read_text(encoding="utf-8")
    paths = [Path(a) for a in sys.argv[1:]] or sorted(
        p for p in REAL.iterdir() if p.suffix.lower() in (".pptx", ".potx")
    )
    report = [run_one(p, outline_text) for p in paths]
    files = [*paths, ROOT / "fixtures" / "reference-outline.md"]
    for r in report:
        files += [ROOT / f for f in r.get("renders", [])] + ([ROOT / r["sheet"]] if "sheet" in r else [])
        name = Path(r["template"]).stem
        if (OUT / name / f"{name}-filled.pptx").exists() and "renders" in r:
            files.append(OUT / name / f"{name}-filled.pptx")
    (OUT / "report.json").write_text(json.dumps({"tested": tested(files), "runs": report}, ensure_ascii=False, indent=1))
    for r in report:
        print(r["template"], r.get("result", "filled"), r.get("code", ""), "script_clean=", r.get("script_clean"))


if __name__ == "__main__":
    main()
