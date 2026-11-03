"""C24 (silent break: no sample text survives) and C27 (silent break: no text lost on the sample route).

The independent oracle (tests/sample_oracle.py) walks every output slide recursively (groups, hidden shapes, fields)
and lists all text by source shape id, with the sample each copy came from and the footers. The list must equal a
hand-written golden per sample fixture (tests/goldens/sample/), in order and count: an extra line is sample text left
behind (C24), a missing, doubled or moved line is text lost or misplaced (C27)."""

from pathlib import Path

import pytest

from conftest import FIX, ROOT
from deckfill import fill, parse_outline, plan_deck, read_template
from sample_oracle import golden, text_lines

OUTLINES = ROOT / "tests" / "outlines" / "sample"
GOLD = ROOT / "tests" / "goldens" / "sample"

CASES = [
    ("sample-design.pptx", "design", None, "design"),
    ("sample-footer.pptx", "footer", {1: "s1", 2: "s2", 3: "s3", 4: "s4"}, "footer"),
    ("sample-footer-nopos.pptx", "only", None, "footer-nopos"),
    ("sample-field.pptx", "field", None, "field"),
    ("sample-hidden.pptx", "hidden", None, "hidden"),
    ("sample-equal.pptx", "equal", None, "equal"),
    ("sample-closing5.pptx", "two-slides", None, "closing5"),
    ("sample-short.pptx", "short", None, "short"),
    ("sample-only.pptx", "four", None, "only"),
    ("sample-connector.pptx", "connector", None, "connector"),
    ("sample-rotated.pptx", "rotated", None, "rotated"),
    ("sample-jump.pptx", "two-slides", None, "jump"),
    ("sample-chart.pptx", "two-slides", None, "chart"),
    ("sample-typo.pptx", "two-slides", None, "typo"),
    ("sample-thin.pptx", "two-slides", None, "thin"),
    ("sample-altcontent.pptx", "two-slides", None, "altcontent"),  # code review F1
    ("sample-ghost.pptx", "ghost", {1: "s2", 2: "s5"}, "ghost"),  # rev 9 T3 echoes, T4 clamps
    ("sample-pairs.pptx", "pairs", {1: "s1", 2: "s1", 3: "s1"}, "pairs"),  # rev 9 T5 pairs
]


def run(fixture: str, outline: str, overrides):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    text = (OUTLINES / f"{outline}.md").read_text(encoding="utf-8")
    plan = plan_deck(info, parse_outline(text), overrides, route="sample")
    return data, fill(data, fixture, plan)


@pytest.mark.parametrize("fixture,outline,overrides,gold", CASES, ids=[c[3] for c in CASES])
def test_c24_c27_text_equals_golden(fixture, outline, overrides, gold):
    data, out = run(fixture, outline, overrides)
    got = text_lines(out, data)
    want = golden(GOLD / f"{gold}.golden")
    extra = [ln for ln in got if ln not in want]
    missing = [ln for ln in want if ln not in got]
    assert not extra, f"C24: text the golden does not hold (sample text left behind?): {extra}"
    assert not missing, f"C27: golden text missing from the output: {missing}"
    assert got == want, f"C27: order or count differs\n got:  {got}\n want: {want}"


def test_c24_override_to_instruction_sample_is_dropped():
    """The font-guide slide (s7) is never copied, even when picked: the pick drops with layout_dropped."""
    data = (FIX / "sample-design.pptx").read_bytes()
    info = read_template(data, "sample-design.pptx")
    text = (OUTLINES / "design.md").read_text(encoding="utf-8")
    plan = plan_deck(info, parse_outline(text), {2: "s7"}, route="sample")
    assert "layout_dropped" in [w.code for w in plan.warnings]
    got = text_lines(fill(data, "sample-design.pptx", plan), data)
    assert got == golden(GOLD / "design.golden")
