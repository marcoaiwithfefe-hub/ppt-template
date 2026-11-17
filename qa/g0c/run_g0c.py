"""G0c (spec map rev 6): Marco's Canva deck (qa/real-templates/canva-red-pink-pitch.pptx) filled with the page's
example outline and with fixtures/reference-outline.md, for both cjk_face values, on the route D11 picks.

Script part, per output: every Chinese run passes C39's rule (tests/rev9_oracle.cjk_problems); no written box crosses
a slide edge (an echo's own bleed aside); the cover's title is written into TextBox 3 (shape id 3), the ghost TextBox 4
echoes it and the cover carries no fit warning; 三個目標 and 預算 are one slide each on a pair or slot destination
(預算's columns are the 2-slot group 4 and 8) with no warning; no slide carries small_text or warned. The C5 validator
result comes from qa/c5/run_validator.py, whose manifest lists these four outputs.

Renders of the unmodified outputs (no East Asian face rewrite): headless LibreOffice, which honours the deck's
embedded fonts, every slide; macOS Quick Look on one-slide copies (it ignores embedded fonts and alpha). Neither
render proves how PowerPoint or Keynote draw the deck. Contact sheets per output go beside them for the eye pass.

    .venv/bin/python qa/g0c/run_g0c.py
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "qa")]

from PIL import Image  # noqa: E402

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402
from provenance import tested  # noqa: E402
import copy  # noqa: E402

from lxml import etree  # noqa: E402
from rev9_oracle import any_chinese, cjk_problems, effective, runs_of  # noqa: E402
from sample_look import boxes, ghost  # noqa: E402
from sample_oracle import a, nv_id, p, parts_of, resolved_paras, slides, tree_of, walk, xml  # noqa: E402

OUT = ROOT / "qa" / "g0c"
TEMPLATE = ROOT / "qa" / "real-templates" / "canva-red-pink-pitch.pptx"
FACES = {"mac": "PingFang HK", "win": "Microsoft JhengHei"}


def example_outline() -> str:
    js = (ROOT / "docs" / "copy.js").read_text(encoding="utf-8")
    block = js[js.index("exampleOutline: ["):js.index('].join("\\n")')]
    return "\n".join(re.findall(r'^\s*"(.*)",\s*$', block, re.M))


OUTLINES = {"example": example_outline(), "reference": (ROOT / "fixtures" / "reference-outline.md").read_text(encoding="utf-8")}


def _canon(rpr) -> bytes:
    e = copy.deepcopy(rpr) if rpr is not None else etree.Element(a("rPr"))
    e.attrib.pop("sz", None)
    return etree.tostring(e, method="c14n")


def donor_problems(plan, out: bytes, src: bytes, face: str) -> list[str]:
    """Codex rev 9 round 1 weak check, C39's donor rule on the Canva outputs: in every box the fill wrote, a run that
    is not a cut Chinese stretch carries its donor's a:rPr (the source box's first run) unchanged apart from sz, and a
    cut stretch carries b="1" when the donor is display text (its effective size at or above 4% of the slide height,
    or effective bold, both resolved here from the source) and the donor's own b otherwise."""
    sp_, op = parts_of(src), parts_of(out)
    sh = int(xml(sp_["ppt/presentation.xml"]).find(p("sldSz")).get("cy"))
    samples = {S.id: S for S in INFO.samples}
    bad = []
    for n, (ps, name) in enumerate(zip(plan.slides, slides(op)), start=1):
        sname = samples[ps.layout].part.lstrip("/")
        src_sp = {nv_id(el)[0]: el for el in walk(tree_of(sp_[sname]))}
        out_sp = {nv_id(el)[0]: el for el in walk(tree_of(op[name]))}
        for bf in ps.boxes:
            s_el, o_el = src_sp[bf.sid], out_sp.get(bf.sid)
            first = next(s_el.iter(a("r")))
            don = first.find(a("rPr"))
            size = resolved_paras(sp_, sname, s_el)[0][1]
            bold = effective(sp_, sname, s_el, first.getparent(), don, "b", "0") in ("1", "true")
            display = size * 12700 >= 4 * sh or bold
            for par in o_el.find(p("txBody")).findall(a("p")):
                for r in runs_of(par):
                    rpr = r.find(a("rPr"))
                    text = r.find(a("t")).text or ""
                    lat = None if rpr is None else rpr.find(a("latin"))
                    cut = (any_chinese(text) and rpr is not None and rpr.get("lang") == "zh-HK" and lat is not None
                           and lat.get("typeface") == face)
                    where = f"slide {n} box {bf.sid} run {text[:12]!r}"
                    if not cut:
                        if _canon(rpr) != _canon(don):
                            bad.append(f"{where}: run properties differ from the donor's apart from sz")
                        continue
                    want = "1" if display else (don.get("b") if don is not None else None)
                    if rpr.get("b") != want:
                        bad.append(f"{where}: b={rpr.get('b')!r}, want {want!r} (display {display})")
    return bad


def checks(plan, out: bytes, face: str, outline: str) -> list[str]:
    bad = list(cjk_problems(out, face)) + donor_problems(plan, out, TEMPLATE.read_bytes(), face)
    op = parts_of(out)
    sz = xml(op["ppt/presentation.xml"]).find(p("sldSz"))
    sw, sh = int(sz.get("cx")), int(sz.get("cy"))
    for n, name in enumerate(slides(op), start=1):
        tree = tree_of(op[name])
        bx = boxes(tree)
        for el in tree.iter(p("sp")):
            sid, _ = nv_id(el)
            text = "".join(t.text or "" for t in el.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"))
            if not text.strip() or sid not in bx or ghost(el):
                continue
            x, y, cx, cy = bx[sid]
            if x < 0 or y < 0 or x + cx > sw or y + cy > sh:
                bad.append(f"slide {n} box {sid} {text[:16]!r} crosses a slide edge: {bx[sid]}")
    cover = plan.slides[0]
    roles = {bf.sid: bf for bf in cover.boxes}
    if cover.layout != "s1" or roles.get(3) is None or roles[3].role != "title":
        bad.append(f"cover: title not in TextBox 3 (sample {cover.layout}, boxes {[(b.sid, b.role) for b in cover.boxes]})")
    if roles.get(4) is None or roles[4].role != "echo":
        bad.append("cover: the ghost TextBox 4 does not echo the title")
    if any(b.status == "warned" for b in cover.boxes):
        bad.append("cover: fit warning")
    for title in ("三個目標", "預算 港幣 800 萬"):
        parts = [ps for ps in plan.slides if ps.title.startswith(title)]
        if len(parts) != 1:
            bad.append(f"{title}: {len(parts)} slides")
            continue
        ps = parts[0]
        dest = [b for b in ps.boxes if b.role in ("head", "slot")] or (
            [b for b in ps.boxes if b.role == "body"] if {b.sid for b in ps.boxes if b.role == "body"} in
            [set(g) for g in next(S for S in INFO.samples if S.id == ps.layout).slots] else [])
        if not dest:
            bad.append(f"{title}: not on a pair or slot destination ({[(b.sid, b.role) for b in ps.boxes]})")
        if "warned" in ps.flags or any(b.status == "warned" for b in ps.boxes):
            bad.append(f"{title}: warned")
    for n, ps in enumerate(plan.slides, start=1):
        for f in ("small_text", "warned"):
            if f in ps.flags:
                bad.append(f"slide {n} {ps.title!r}: {f}")
    return bad


def lo_render(deck: Path, out: Path, tmp: Path) -> None:
    """Headless LibreOffice on the unmodified deck, a private profile, PDF then PNG pages."""
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="lo-", dir=tmp))
    subprocess.run(["/opt/homebrew/bin/soffice", f"-env:UserInstallation=file://{work / 'profile'}", "--headless",
                    "--convert-to", "pdf", "--outdir", str(work), str(deck)], check=True, capture_output=True, timeout=600)
    subprocess.run(["/opt/homebrew/bin/pdftoppm", "-r", "50", "-png", str(work / (deck.stem + ".pdf")), str(out / "slide")],
                   check=True)


def one_slide(data: bytes, keep: int) -> bytes:
    """The deck with only slide keep (1-based) left in the presentation's slide list (the other parts stay)."""
    zin = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            b = zin.read(info.filename)
            if info.filename == "ppt/presentation.xml":
                ids = re.findall(rb"<p:sldId [^>]*/>", b)
                for k, e in enumerate(ids, start=1):
                    if k != keep:
                        b = b.replace(e, b"", 1)
            z.writestr(info, b)
    return buf.getvalue()


def ql_render(deck: Path, out: Path, n: int, tmp: Path) -> None:
    """macOS Quick Look thumbnails at 1600 px of one-slide copies (ignores embedded fonts and alpha)."""
    out.mkdir(parents=True, exist_ok=True)
    data = deck.read_bytes()
    work = Path(tempfile.mkdtemp(prefix="ql-", dir=tmp))
    for k in range(1, n + 1):
        one = work / f"slide-{k}.pptx"
        one.write_bytes(one_slide(data, k))
        subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", str(work), str(one)], check=True, capture_output=True, timeout=120)
        shutil.move(str(work / f"slide-{k}.pptx.png"), out / f"slide-{k}.png")


def sheet(pngs: list[Path], dst: Path, cols: int = 3, w: int = 640) -> None:
    ims = [Image.open(x).convert("RGB") for x in pngs]
    ims = [im.resize((w, round(im.height * w / im.width))) for im in ims]
    h = max(im.height for im in ims)
    rows = -(-len(ims) // cols)
    canvas = Image.new("RGB", (cols * w + (cols - 1) * 8, rows * h + (rows - 1) * 8), "white")
    for i, im in enumerate(ims):
        canvas.paste(im, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
    canvas.save(dst)


def main() -> int:
    global INFO
    data = TEMPLATE.read_bytes()
    INFO = read_template(data, TEMPLATE.name)
    tmp = Path(tempfile.mkdtemp(prefix="g0c-tmp-", dir=OUT))  # this run's own scratch
    rows, failed = [], 0
    for oname, text in OUTLINES.items():
        for ua, face in FACES.items():
            tag = f"{oname}-{ua}"
            plan = plan_deck(INFO, parse_outline(text), None, cjk_face=face)
            out = fill(data, TEMPLATE.name, plan)
            deck = OUT / "out" / f"canva-{tag}.pptx"
            deck.parent.mkdir(parents=True, exist_ok=True)
            deck.write_bytes(out)
            bad = checks(plan, out, face, oname)
            failed += bool(bad)
            lo_render(deck, OUT / "renders" / tag / "libreoffice", tmp)
            ql_render(deck, OUT / "renders" / tag / "quicklook", len(plan.slides), tmp)
            for kind in ("libreoffice", "quicklook"):
                pngs = sorted((OUT / "renders" / tag / kind).glob("slide-*.png"), key=lambda x: int(re.findall(r"\d+", x.stem)[-1]))
                sheet(pngs, OUT / f"sheet-{tag}-{kind}.png")
            rows.append({"outline": oname, "cjk_face": face, "route": plan.route, "output": str(deck.relative_to(ROOT)),
                         "slides": [{"sample": ps.layout, "title": ps.title, "fit": ps.fit, "flags": list(ps.flags),
                                     "boxes": [[b.sid, b.role, b.sizes[0], b.status] for b in ps.boxes]} for ps in plan.slides],
                         "problems": bad, "ok": not bad})
            print("PASS" if not bad else "FAIL", tag, f"{len(plan.slides)} slides", *bad[:5])
    # the run's scratch (qa/g0c/g0c-tmp-*, gitignored) is left in place: no deletes from QA scripts (seat rules)
    src = sorted((ROOT / "src" / "deckfill").glob("*.py")) + [TEMPLATE]
    (OUT / "g0c-report.json").write_text(json.dumps({"tested": tested(src), "rows": rows},
                                                    indent=1, ensure_ascii=False))
    print(f"{len(rows) - failed} of {len(rows)} outputs pass the G0c script checks")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
