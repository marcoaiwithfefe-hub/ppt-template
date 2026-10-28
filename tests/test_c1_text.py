"""C1, silent break: no text lost. Golden files are hand-written from D2 (tests/goldens)."""

import pytest
from conftest import GOLDENS, outline_text
from oracle import deck_lines, read_deck, read_golden

from deckfill import fill, parse_outline, plan_deck, read_template

CASES = [
    # (outline, template, golden)
    ("reference", "typed.pptx", "reference"),
    ("reference", "custom.pptx", "reference"),
    ("reference", "wui-tung.pptx", "reference"),
    ("reference", "wui-tung.potx", "reference"),
    ("reference", "two-masters.pptx", "reference"),
    ("reference", "sections.pptx", "reference"),
    ("reference", "footer-active.pptx", "reference"),
    ("reference", "contradict.pptx", "reference"),
    ("marks", "typed.pptx", "marks"),
    ("structure", "typed.pptx", "structure"),
    ("structure-cr", "typed.pptx", "structure"),
    ("no-title", "typed.pptx", "no-title"),
    ("english", "typed.pptx", "english"),
    # D3 step 4 fallbacks, run with non-empty content
    ("reference", "no-two.pptx", "reference.merged"),
    ("reference", "no-section.pptx", "reference"),
    ("reference", "no-title.pptx", "reference.title-in-body"),
    ("reference", "only-content.pptx", "reference.only-content"),
]


def run(outline_name, template):
    text = outline_text(outline_name)
    return run_text(text, template)


def run_text(text, template_bytes, name="t.pptx", overrides=None):
    info = read_template(template_bytes, name)
    outline = parse_outline(text)
    plan = plan_deck(info, outline, overrides)
    return outline, plan, fill(template_bytes, name, plan)


@pytest.mark.parametrize("outline_name,template,golden", CASES)
def test_text_lands_where_golden_says(outline_name, template, golden, tpl):
    content, warns, planwarns = read_golden(GOLDENS / f"{golden}.golden")
    outline, plan, out = run(outline_name, tpl(template))
    assert deck_lines(read_deck(out)) == content
    assert [f"warn {w.line} {w.code}" for w in outline.warnings] == warns
    plan_only = list(plan.warnings[len(outline.warnings):])
    assert [f"planwarn {w.line} {w.code}" for w in plan_only] == planwarns


def test_every_d2_bullet_mark_is_removed():
    o = parse_outline("## t\n" + "\n".join(f"{m}x" for m in ["- ", "* ", "•", "·", "‧", "1. ", "1) ", "1、", "一、"]))
    assert [it.text for it in o.slides[0].columns[0]] == ["x"] * 9


def test_marks_that_are_text_stay_text():
    o = parse_outline("## t\n-5% 成本\n1.5 億\n*重要*\n2.0x")
    assert [it.text for it in o.slides[0].columns[0]] == ["-5% 成本", "1.5 億", "*重要*", "2.0x"]


def test_indents():
    o = parse_outline("## t\n- a\n  - b\n\t- c\n　- d\n - e\n        - f")
    assert [(it.level, it.text) for it in o.slides[0].columns[0]] == [
        (1, "a"), (2, "b"), (2, "c"), (2, "d"), (1, "e"), (2, "f"),
    ]


def test_bom_crlf_cr_same_result():
    base = "# T\n副題\n## A\n- x\n"
    a = parse_outline(base)
    assert parse_outline("﻿" + base.replace("\n", "\r\n")) == a
    assert parse_outline(base.replace("\n", "\r")) == a


def test_control_characters_do_not_reach_the_deck(tpl):
    _, _, out = run_text("## t\n- a\x00b\x0bc", tpl("typed.pptx"))
    assert "slide 1 body1 L1 abc" in deck_lines(read_deck(out))
