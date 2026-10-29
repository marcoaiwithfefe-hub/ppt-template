"""D10: the 匯通物流 demo deck for the reel.

The outline is Gemini's answer to the reference report (C15 run, qa/gemini/wui-tung-report.out.txt),
filled into fixtures/wui-tung-template.pptx. Writes qa/demo/wui-tung-outline.md,
qa/demo/wui-tung-deck.pptx, per-slide renders, a contact sheet and qa/demo/demo-report.json
with the C1, C3 and C5 integrity results (C20).

Run: .venv/bin/python qa/demo/make_demo.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "qa" / "g0"))

from oracle import kept_part_problems, new_parts, parts_of, read_deck  # noqa: E402
from run_g0 import actual_sequence, contact_sheet, expected_sequence, render_slides, same_sequence  # noqa: E402

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402
from deckfill.package import check_integrity  # noqa: E402

DEMO = ROOT / "qa" / "demo"


def main() -> None:
    answer = (ROOT / "qa" / "gemini" / "wui-tung-report.out.txt").read_text(encoding="utf-8")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", answer, re.S)
    assert len(blocks) == 1, "expected one code block in Gemini's answer"
    text = blocks[0]
    (DEMO / "wui-tung-outline.md").write_text(text, encoding="utf-8")

    data = (ROOT / "fixtures" / "wui-tung-template.pptx").read_bytes()
    info = read_template(data, "wui-tung-template.pptx")
    outline = parse_outline(text)
    plan = plan_deck(info, outline)
    out = fill(data, "wui-tung-template.pptx", plan)
    deck_path = DEMO / "wui-tung-deck.pptx"
    deck_path.write_bytes(out)

    names = {lay.id: lay.name for lay in info.layouts}
    rec = {
        "slides": [f"{s.title} -> {names[s.layout]} ({s.fit})" for s in plan.slides],
        "warnings": [f"{w.line} {w.code}" for w in plan.warnings],
        "c1_round_trip": same_sequence(expected_sequence(outline), actual_sequence(read_deck(out))),
        "c3_kept_problems": kept_part_problems(data, out),
        "c3_unexpected_new_parts": [n for n in new_parts(data, out) if not n.startswith("ppt/slides/")],
        "c5_integrity": check_integrity(parts_of(out)),
        "c5_validator": "NOT RUN: Open XML SDK not installed",
    }
    pngs = render_slides(deck_path, DEMO / "renders")
    rec["renders"] = [str(p.relative_to(ROOT)) for p in pngs]
    contact_sheet(pngs, DEMO / "wui-tung-sheet.png", f"wui-tung-deck.pptx: {len(pngs)} slides")
    (DEMO / "demo-report.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k != "renders"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
