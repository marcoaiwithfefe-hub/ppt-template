"""Failure demos for the silent-break checks (spec rows C1, C2, C4, C5 integrity part).

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
}


def pytest(args: list[str]) -> str:
    if args[0] == "node":  # end-to-end check (C9): FAIL lines and the summary
        run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env={**os.environ, "IDLE_MS": "3000"})
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
        (OUT / f"{key}-mutated.txt").write_text(head + pytest(args), encoding="utf-8")
    finally:
        path.write_text(original, encoding="utf-8")
    (OUT / f"{key}-fixed.txt").write_text(head + pytest(args), encoding="utf-8")


if __name__ == "__main__":
    for k in sys.argv[1:] or DEMOS:
        demo(k)
        print(k, "done")
