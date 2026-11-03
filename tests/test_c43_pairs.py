"""C43 (heading and body pairs, T5) on sample-pairs, plus the pair-destination clamp of C42.

Expectations are written by hand from T5 and the fixture's geometry (fixtures/make_rev9_fixtures.py make_pairs, in
points on a 1440 by 810 pt slide): p1 Marco's slide 2, p2 his slide 7, p3 simple-business s7, p4 business-conference
s7, p5 Marco's year template s5, p6 p1 with 01 labels. The C24 and C27 golden 'pairs' holds the text, order, levels
and labels; the negative demos (C43 through C27) mutate the pair destination and show the golden comparison fail."""

import pytest

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from sample_look import boxes, look_diff
from sample_oracle import golden, parts_of, slides, text_lines, tree_of
from test_c24_c27_sample_text import GOLD, OUTLINES

NAME = "sample-pairs.pptx"
PT = 12700


def E(*v):
    return tuple(int(round(x * PT)) for x in v)


def run(text, ovr):
    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    plan = plan_deck(info, parse_outline(text), ovr, route="sample")
    return data, info, plan, fill(data, NAME, plan)


def roles(plan, n):
    return {bf.sid: bf.role for bf in plan.slides[n].boxes}


def out_box(out, n, sid):
    op = parts_of(out)
    return boxes(tree_of(op[slides(op)[n - 1]]))[sid]


LONG = "本地送貨準時率由今年第一季開始逐步提升，目標係全年平均達到百分之九十七，同時減少重新派送嘅次數"


def test_c43_reading():
    info = read_template((FIX / NAME).read_bytes(), NAME)
    S = {s.id: s for s in info.samples}
    assert S["s1"].pair_groups == (((111, 121), (112, 122), (113, 123)),)
    assert dict(S["s1"].pair_labels) == {111: 131, 112: 132, 113: 133}
    assert S["s2"].pair_groups == (((211, 221), (212, 222), (213, 223)),), "slide 7 pairs although H widths differ"
    assert set(S["s3"].pair_groups) == {((311, 321), (312, 322)), ((312, 322), (313, 323))}
    assert "two" in S["s1"].classes


def test_c43_golden_and_look():
    data, _, plan, out = run((OUTLINES / "pairs.md").read_text(encoding="utf-8"), {1: "s1", 2: "s1", 3: "s1"})
    assert text_lines(out, data) == golden(GOLD / "pairs.golden")
    assert look_diff(out, data) == []
    # content: H1 to the pair union's x and width, from H's top to B's top; B1 widened to the union
    assert out_box(out, 2, 111) == E(81, 566, 375, 36)
    assert out_box(out, 2, 121) == E(81, 602, 375, 128)
    # two columns: each used H is its pair's union
    assert out_box(out, 3, 111) == E(81, 566, 375, 164)
    assert out_box(out, 3, 112) == E(532, 566, 375, 164)


def test_c43_four_bullets_no_pairs():
    _, _, plan, _ = run("# Deck\n\n## Four\n- a\n- b\n- c\n- d\n", {1: "s1"})
    assert "head" not in roles(plan, 1).values()


def test_c43_built_columns_that_pass_keep_them():
    _, _, plan, _ = run("# Deck\n\n## 預算\n- 科技 350 萬\n- 車隊 300 萬\n||\n- 科技佔 44%\n- 車隊佔 37%\n", {1: "s2"})
    r = roles(plan, 1)
    assert r.get(211) == "body" and r.get(212) == "body" and "head" not in r.values()


def test_c43_simple_business_columns_take_the_horizontal_group():
    _, _, plan, _ = run("# Deck\n\n## Cols\n- 科技 350 萬\n||\n- 科技佔 44%\n", {1: "s3"})
    r = roles(plan, 1)
    assert r.get(311) == "head" and r.get(312) == "head" and 313 not in r


def test_c43_overlapping_groups_tie_rule():
    """Two pair groups of two (horizontal 311/321 + 312/322 and stacked 312/322 + 313/323); the bullets cannot sit in
    the heading slots (R7), both pair groups qualify, so the larger total area of the pairs' unions wins: stacked."""
    _, _, plan, _ = run(f"# Deck\n\n## Two\n- {LONG}\n- {LONG}\n", {1: "s3"})
    r = roles(plan, 1)
    assert r.get(312) == "head" and r.get(313) == "head" and 311 not in r


def test_c43_slots_that_qualify_ignore_pairs():
    _, _, plan, _ = run("# Deck\n\n## Steps\n- One\n- Two\n- Three\n- Four\n", {1: "s4"})
    assert [bf.sid for bf in plan.slides[1].boxes if bf.role == "slot"] == [421, 422, 423, 424]
    _, _, plan, _ = run("# Deck\n\n## Top\n- One\n- Two\n- Three\n", {1: "s5"})
    assert [bf.sid for bf in plan.slides[1].boxes if bf.role == "slot"] == [521, 522, 523]


def test_c43_label_format_kept():
    _, _, plan, out = run("# Deck\n\n## Two\n- 本地送貨準時率：92% 升到 97%\n- 葵涌倉存貨周轉：45 日減到 35 日\n", {1: "s6"})
    labels = {bf.sid: bf.paras[0][1] for bf in plan.slides[1].boxes if bf.role == "label"}
    assert labels == {631: "01", 632: "02"}


def test_c43_box_that_cannot_fit_disqualifies():
    child = "細節 " * 400
    _, _, plan, _ = run(f"# Deck\n\n## Two\n- 一\n  - {child}\n- 二\n", {1: "s1"})
    assert "head" not in roles(plan, 1).values()


# --- negative demos: a pair destination drops or moves a child bullet (C43 through C27) -----------------------------


@pytest.mark.parametrize("how", ["drop", "move"])
def test_c43_negative_child_dropped_or_moved(monkeypatch, how):
    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    import deckfill.sample_plan as spl

    orig = spl.pairs_for

    def wrapped(S, items):
        got = orig(S, items)
        if got is None:
            return got
        fills, used = got
        out = []
        for bf in fills:
            if bf.role == "pbody" and how == "drop":
                continue
            if bf.role == "pbody" and how == "move":
                bf = spl.BoxFill(bf.sid + 1, bf.role, bf.paras, bf.sizes, bf.step, bf.status, None)
            out.append(bf)
        return tuple(out), used
    monkeypatch.setattr(spl, "pairs_for", wrapped)
    plan = plan_deck(info, parse_outline((OUTLINES / "pairs.md").read_text(encoding="utf-8")), {1: "s1", 2: "s1", 3: "s1"},
                     route="sample")
    out = fill(data, NAME, plan)
    assert text_lines(out, data) != golden(GOLD / "pairs.golden")


# --- C42's pair part: a pair destination crossing an edge is clamped ------------------------------------------------


def test_c42_pair_destination_clamped():
    """p6's third body (1100 pt, 375 pt wide) crosses the right edge: T4 pulls it to the content margin (the title's
    82 pt), so its pair union and the boxes T5 writes stay on the slide, and C23 accepts them."""
    data, _, plan, out = run("# Deck\n\n## Three\n- 一\n- 二\n- 三\n  - 細\n", {1: "s6"})
    assert out_box(out, 2, 623) == E(1100, 602, 258, 128)
    assert out_box(out, 2, 613) == E(1100, 566, 258, 36)
    assert look_diff(out, data) == []
