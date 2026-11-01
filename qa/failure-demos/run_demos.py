"""Failure demos for the silent-break checks (spec rows C1, C2, C4, C5 integrity part; rev 8: C24, C26, C27; code
review round 1: F1, F2, F6).

Each demo applies one isolated mutation to the source, runs the check's tests, restores the
file, and runs the tests again. Output: qa/failure-demos/<id>-mutated.txt and <id>-fixed.txt.

Run: .venv/bin/python qa/failure-demos/run_demos.py [id ...]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "qa" / "failure-demos"

DEMOS = {
    "c1-text-lost": (
        "fill drops the last paragraph of every body",
        "src/deckfill/fill.py",
        "_put(shapes[idx], paras)",
        "_put(shapes[idx], paras[:-1])",
        ["tests/test_c1_text.py"],
    ),
    "c2-column-order": (
        "two-column layouts order columns by XML order instead of by x",
        "src/deckfill/template.py",
        "left, right = sorted((a, b), key=lambda b_: b_.x)",
        "left, right = sorted((a, b), key=lambda b_: bodies.index(b_))",
        ["tests/test_c2_layouts.py"],
    ),
    "c3-rels-order": (
        "fill keeps python-pptx's re-sorted, relativised relationships instead of the template's own",
        "src/deckfill/fill.py",
        "    parts = _restore_kept(pkg.parts, parts, pkg.main)",
        "    pass",
        ["tests/test_c3_c6_package.py", "-k", "every_kept_part_unchanged and rels-order"],
    ),
    "c4-footers": (
        "no footer or slide number is ever added to a new slide",
        "src/deckfill/fill.py",
        '    """D4 footer rules for one new slide. Returns shape elements to add."""\n    out = []',
        '    """D4 footer rules for one new slide. Returns shape elements to add."""\n    return []\n    out = []',
        ["tests/test_c4_footers.py"],
    ),
    "c4-slidenum-text": (
        "a copied slide-number field keeps its source slide's cached text",
        "src/deckfill/fill.py",
        "            _number_slidenum_fields(el, number)\n",
        "",
        ["tests/test_c4_footers.py"],
    ),
    "c5-integrity": (
        "the integrity check stops checking relationship attributes (r:id, r:embed, ...)",
        "src/deckfill/package.py",
        'if attr.startswith("{%s}" % R_NS) and value and value not in rels:',
        "if False:",
        ["tests/test_c3_c6_package.py", "-k", "c5"],
    ),
    "c9-fetch-after-download": (
        "the page fetches a same-origin file one second after each download",
        "docs/app.js",
        '  $("downloaded").hidden = false;\n}',
        '  $("downloaded").hidden = false;\n  setTimeout(() => fetch("./copy.js").catch(() => {}), 1000);\n}',
        ["node", "tests/e2e/c9_privacy.mjs"],
    ),
    "c9-outline-in-link": (
        "the Gemini link carries the start of the outline in its URL",
        "docs/app.js",
        '  $("download-label").textContent = fmt(COPY.download, { name: p.name });',
        '  $("download-label").textContent = fmt(COPY.download, { name: p.name });\n'
        '  document.querySelector(\'a[href^="https://gemini"]\').href =\n'
        '    "https://gemini.google.com/app?q=" + encodeURIComponent($("outline").value.slice(0, 60));',
        ["node", "tests/e2e/c9_privacy.mjs"],
    ),
    # rev 8, sample route
    "c24-box-uncleared": (
        "nothing that received no outline text is cleared on a copy",
        "src/deckfill/sample_fill.py",
        "if sid in fills or sid in removed:",
        "if True:",
        ["tests/test_c24_c27_sample_text.py"],
    ),
    "c24-hidden-left": (
        "hidden shapes keep their sample text on the copy",
        "src/deckfill/sample_fill.py",
        "            if sid in fills or sid in removed:\n                continue",
        "            if sid in fills or sid in removed:\n                continue\n            if w.hidden:\n                continue",
        ["tests/test_c24_c27_sample_text.py"],
    ),
    "c24-instruction-copied": (
        "instruction slides are not excluded, so a pick of the font guide is copied",
        "src/deckfill/sample.py",
        "    elif instruction(all_text):",
        "    elif False:",
        ["tests/test_c24_c27_sample_text.py"],
    ),
    "c26-link-kept": (
        "an element using a link to a removed slide stays on the copy (its relationship is not copied)",
        "src/deckfill/sample_fill.py",
        "            if v in dead:",
        "            if False:",
        ["tests/test_c26_c29_c30_sample.py", "-k", "c26"],
    ),
    "c27-bullet-omitted": (
        "the last paragraph of every multi-paragraph box is not written",
        "src/deckfill/sample_fill.py",
        "    for lvl, text in bf.paras:",
        "    for lvl, text in bf.paras[:-1] or bf.paras:",
        ["tests/test_c24_c27_sample_text.py"],
    ),
    "c27-bullet-duplicated": (
        "the last paragraph of every box is written twice",
        "src/deckfill/sample_fill.py",
        "    for lvl, text in bf.paras:",
        "    for lvl, text in bf.paras + bf.paras[-1:]:",
        ["tests/test_c24_c27_sample_text.py"],
    ),
    "c27-wrong-slot": (
        "slot bullets go to the slots in reverse reading order",
        "src/deckfill/sample_plan.py",
        'fills = [fill_box(S.box(sid), "slot", g) for sid, g in zip(slots, groups)]',
        'fills = [fill_box(S.box(sid), "slot", g) for sid, g in zip(slots[::-1], groups)]',
        ["tests/test_c24_c27_sample_text.py"],
    ),
    # code review round 1
    "f1-choice-kept": (
        "a copy keeps every mc:AlternateContent whole, choice branches included",
        "src/deckfill/sample_fill.py",
        "    normalise_alternates(csld)  # code review F1: the fallback branches only, as the reader classified them\n",
        "",
        ["tests/test_c24_c27_sample_text.py", "tests/test_cr1_code_review.py", "-k", "altcontent or f1"],
    ),
    "f6-inherited-size": (
        "the reader skips the layout placeholder when it resolves a placeholder's inherited size and spacing",
        "src/deckfill/sample.py",
        "            out.append(lvl_ppr(_lst(lay_sp), level))",
        "            pass",
        ["tests/test_c25_fit.py"],
    ),
    "f6-level2-ppr-dropped": (
        "level-2 paragraphs are written without their paragraph properties",
        "src/deckfill/sample_fill.py",
        "            ppr = copy.deepcopy(l2_ppr)",
        "            ppr = None",
        ["tests/test_c25_fit.py"],
    ),
    "e2-picks-kept-on-switch": (
        "a route switch forgets picks only at the next successful plan",
        "docs/app.js",
        '  state.overrides = state.overrides.map((o) => ({ ...o, route: "switched" }));\n',
        "",
        ["node", "tests/e2e/c9_privacy.mjs"],
    ),
    "f2-guide-path": (
        "a custom path's guide-name corner is read as an integer",
        "src/deckfill/sample.py",
        "return int(v) if v is not None and _INT.fullmatch(v.strip()) else None",
        "return int(v or 0)",
        ["tests/test_cr1_code_review.py", "-k", "f2"],
    ),
    "f2-sample-isolation": (
        "an error while reading one sample slide aborts the whole template",
        "src/deckfill/sample.py",
        "            out.append(unreadable(k, slide, _why(e)))\n    return tuple(out)",
        "            raise\n    return tuple(out)",
        ["tests/test_cr1_code_review.py", "-k", "f2"],
    ),
}


def pytest(args: list[str], tag: str = "") -> str:
    if args[0] == "node":  # end-to-end check (C9): FAIL lines and the summary
        # its own output folder, so a demo run never overwrites the evidence run in qa/e2e
        env = {**os.environ, "E2E_OUT": str(OUT / "runs" / tag)}
        run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
        lines = (run.stdout + run.stderr).strip().splitlines()
        return "\n".join([ln for ln in lines if ln.startswith("FAIL")] + lines[-1:]) + "\n"
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=ROOT, capture_output=True, text=True,
    )
    lines = (run.stdout + run.stderr).strip().splitlines()
    failed = [ln for ln in lines if ln.startswith("FAILED")]
    return "\n".join(failed + lines[-1:]) + "\n"


def demo(key: str) -> None:
    what, rel, old, new, args = DEMOS[key]
    path = ROOT / rel
    original = path.read_text(encoding="utf-8")
    assert original.count(old) == 1, f"{key}: mutation target not found exactly once in {rel}"
    head = f"# {key}: {what}\n# mutation in {rel}: {old!r} -> {new!r}\n# tests: {' '.join(args)}\n"
    try:
        path.write_text(original.replace(old, new), encoding="utf-8")
        (OUT / f"{key}-mutated.txt").write_text(head + pytest(args, f"{key}-mutated"), encoding="utf-8")
    finally:
        path.write_text(original, encoding="utf-8")
    (OUT / f"{key}-fixed.txt").write_text(head + pytest(args, f"{key}-fixed"), encoding="utf-8")


if __name__ == "__main__":
    for k in sys.argv[1:] or DEMOS:
        demo(k)
        print(k, "done")
