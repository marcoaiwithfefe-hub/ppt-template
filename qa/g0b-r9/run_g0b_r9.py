"""G0b-r9 (spec map rev 6): G0b re-run at the build head with round 3's checks, for both cjk_face values, beside
round 3's report at 2ae997b (git show 2ae997b:qa/g0b/<template>/report.json).

Fails when, against round 3: a template's slide count rises; an outline slide gains a continuation; a slide newly
carries check-this-slide; a slide newly carries warned or small_text, unless T2's line-height floor is the only cause
(each such slide is listed for Fable's eye, an eye verdict on the unmodified render). Picks that change are listed with the round 3 sheet and
this run's sheets. Geometry sheets come from qa/g0b/lo_render.py (East Asian faces rewritten to Arial Unicode MS:
geometry only); typeface evidence comes only from the unmodified LibreOffice sheets (no rewrite).

    .venv/bin/python qa/g0b-r9/run_g0b_r9.py
"""

from __future__ import annotations

import functools
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "qa")]

from deckfill import plan_deck  # noqa: E402
from provenance import tested  # noqa: E402

OUT = ROOT / "qa" / "g0b-r9"
BASE = "2ae997b"
FACES = {"mac": "PingFang HK", "win": "Microsoft JhengHei"}
NEW_BAD = {"warned", "small_text", "check"}

spec = importlib.util.spec_from_file_location("run_g0b", ROOT / "qa" / "g0b" / "run_g0b.py")
g0b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g0b)


def baseline(tag: str) -> dict:
    return json.loads(subprocess.run(["git", "show", f"{BASE}:qa/g0b/{tag}/report.json"], cwd=ROOT, capture_output=True,
                                     text=True, check=True).stdout)


def unmodified_sheet(deck: Path, d: Path, n: int) -> str:
    """Headless LibreOffice on the deck as delivered (no face rewrite), one contact sheet."""
    work = Path(tempfile.mkdtemp(prefix="unmodified-", dir=d))
    subprocess.run(["/opt/homebrew/bin/soffice", f"-env:UserInstallation=file://{work / 'profile'}", "--headless",
                    "--convert-to", "pdf", "--outdir", str(work), str(deck)], check=True, capture_output=True, timeout=900)
    subprocess.run(["/opt/homebrew/bin/pdftoppm", "-r", "36", "-png", str(work / (deck.stem + ".pdf")), str(work / "slide")], check=True)
    pngs = sorted(work.glob("slide-*.png"), key=lambda f: int(re.findall(r"\d+", f.stem)[-1]))
    assert len(pngs) == n, f"{deck.name}: {len(pngs)} pages for {n} slides"
    rows = -(-n // 4)
    sheet = d / "sheet-unmodified.jpg"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-y", "-pattern_type", "glob", "-i", str(work / "slide-*.png"),
                    "-vf", f"scale=480:-2,tile=4x{rows}:padding=6:color=white", "-frames:v", "1", "-q:v", "4", str(sheet)], check=True)
    return str(sheet.relative_to(ROOT))


def compare(new: dict, old: dict) -> dict:
    fails, eye = [], []
    if len(new["slides"]) > len(old["slides"]):
        fails.append(f"slide count {len(old['slides'])} -> {len(new['slides'])}")
    for title, k in (new.get("per_outline_slide") or {}).items():
        was = (old.get("per_outline_slide") or {}).get(title)
        if was is not None and k > was:
            fails.append(f"{title!r} gains a continuation: {was} -> {k}")
    seen: dict[str, int] = {}
    old_by = {}
    for s in old["slides"]:
        i = seen.get(s["title"], 0)
        seen[s["title"]] = i + 1
        old_by[(s["title"], i)] = set(s.get("flags", []))
    seen = {}
    for s in new["slides"]:
        i = seen.get(s["title"], 0)
        seen[s["title"]] = i + 1
        added = (set(s.get("flags", [])) - old_by.get((s["title"], i), set())) & NEW_BAD
        if "check" in added:  # T2's line-height floor cannot cause check-this-slide: a plain failure
            fails.append(f"slide {s['n']} {s['title']!r} newly carries check")
        if added - {"check"}:  # warned or small_text: fails unless T2's floor is the only cause (Fable's eye)
            eye.append({"slide": s["n"], "title": s["title"], "sample": s["sample"], "new_flags": sorted(added - {"check"})})
    picks = [{"outline_slide": k, "before": b, "after": a} for k, (b, a) in enumerate(zip(old["chosen"], new["chosen"])) if a != b]
    return {"fails": fails, "new_flags_for_eye": eye, "picks_changed": picks}


def main() -> int:
    rows, failed = [], 0
    for ftag, face in FACES.items():
        g0b.OUT = OUT / ftag
        g0b.plan_deck = functools.partial(plan_deck, cjk_face=face)
        for name in g0b.SET:
            tag = Path(name).stem
            r = g0b.run(name, None, tag)
            old = baseline(tag)
            c = compare(r, old)
            d = OUT / ftag / tag
            c["sheet_geometry"] = r["sheet"]
            c["sheet_unmodified"] = unmodified_sheet(d / f"{tag}-filled.pptx", d, len(r["slides"]))
            c["sheet_round3"] = f"{BASE}:qa/g0b/{tag}/sheet.jpg"
            row = {"template": name, "cjk_face": face, "slides": [len(old["slides"]), len(r["slides"])],
                   "per_outline_slide": r.get("per_outline_slide"), "title_slide": r.get("title_slide"),
                   "two_column_slide": r.get("two_column_slide"), "new_overlaps": len(r.get("new_overlaps", [])),
                   "blank_chips": len(r.get("blank_chips", [])), "c23_diffs": r.get("c23_diffs"),
                   "title_bar": r.get("title_bar"), "closing_bar": r.get("closing_bar"), **c}
            bad = bool(c["fails"]) or bool(r.get("c23_diffs"))
            failed += bad
            rows.append(row)
            print("FAIL" if bad else "PASS", ftag, tag, f"slides {len(old['slides'])}->{len(r['slides'])}",
                  "eye", len(c["new_flags_for_eye"]), "picks changed", len(c["picks_changed"]), *c["fails"], flush=True)
    src = sorted((ROOT / "src" / "deckfill").glob("*.py"))
    (OUT / "g0b-r9-report.json").write_text(json.dumps({"tested": tested(src), "baseline": BASE, "rows": rows},
                                                        ensure_ascii=False, indent=1))
    print(f"{len(rows) - failed} of {len(rows)} runs pass the script half; slides for the eye: "
          f"{sum(len(r['new_flags_for_eye']) for r in rows)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
