"""C44 (title growth and the display floor, T6) on sample-titlegrow (1440 by 810 pt).

Expected boxes are computed by hand from T6 and the fixture (fixtures/make_rev9_fixtures.py make_titlegrow): R3's
64 by 36 grid (22.5 pt cells), cells within 4% of an edge taken, the Blank layout's three footer boxes at y 500 to 529
pt (x 36 to 684 pt) taken, every destination taking its final box, watermarks and the title's own boxes taking none."""

import pytest

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.sample_plan import display_floor, scaled
from sample_look import boxes, look_diff
from sample_oracle import parts_of, slides, tree_of
from test_c25_fit import floor_ok

NAME = "sample-titlegrow.pptx"
PT = 12700
SH = 10287000


def E(*v):
    return tuple(int(round(x * PT)) for x in v)


def run(text, ovr=None):
    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    plan = plan_deck(info, parse_outline(text), ovr, route="sample")
    return data, info, plan, fill(data, NAME, plan)


def title_of(plan, n):
    return next(bf for bf in plan.slides[n].boxes if bf.role == "title")


def hits(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


FOOTERS = [E(36, 500.5, 168, 28.75), E(246, 500.5, 228, 28.75), E(516, 500.5, 168, 28.75)]


def test_c44_cover_grows():
    data, info, plan, out = run("# 匯通物流 2027 年度計劃\n營運部 · 內部簡報\n")
    t = title_of(plan, 0)
    assert t.box is not None and t.box[:2] == E(70, 110), "the grown title keeps the title box's exact top-left"
    assert t.status in ("fits", "shrunk"), "the cover carries no fit warning"
    for taken in [E(1300, 40, 60, 60), E(944, 702, 416, 31)] + FOOTERS:
        assert not hits(t.box, taken), f"grown title {t.box} covers {taken}"
    assert hits(t.box, E(868, 275, 730, 596)), "the ghost takes no cells"
    assert floor_ok("title", 29700, t.sizes[0] or 29700, SH)
    assert look_diff(out, data) == []


def test_c44_narrower_box_beside_the_logo():
    data, _, plan, out = run("# Deck\n\n## 市場策略 2027 全面拓展\n- Body\n", {1: "s2"})
    t = title_of(plan, 1)
    assert t.box is not None and t.box[:2] == E(70, 84)
    assert t.box[2] < E(1300)[0], "a rectangle narrower than the box is chosen"
    assert not hits(t.box, E(1100, 60, 150, 150))
    assert look_diff(out, data) == []


def test_c44_not_tried_when_title_fits():
    _, _, plan, _ = run("# Deck\n\n## OK\n- Body\n", {1: "s3"})
    assert title_of(plan, 1).box is None


def test_c44_eighty_point_title_keeps_seventy_percent():
    _, _, plan, _ = run("# Deck\n\n## Implementation plan 2027 年度實施計劃\n- Body\n", {1: "s4"})
    t = title_of(plan, 1)
    assert t.sizes[0] == 0 or t.sizes[0] >= 5600


def test_c44_ties_go_to_larger_area():
    _, _, plan, _ = run("# Deck\n\n## OPEN DOOR POLICY 開放\n- Body\n", {1: "s5"})
    t = title_of(plan, 1)
    assert t.box is not None, "grows"
    assert t.box[0] + t.box[2] == 61 * 18288000 // 64, "the widest (largest) rectangle wins the tie"
    # rev 9 QA round 1 Q9-3: the grown box is 1258 pt inside its insets; at 120 pt "OPEN DOOR POLICY 開" takes
    # 1242 pt and leaves 放 alone, at 114 pt the title (1293.9 pt) still leaves it alone, at 108 pt (1225.8 pt) it
    # sets one line
    assert t.sizes[0] == 10800


def test_c44_two_backings_no_growth():
    _, _, plan, _ = run("# Deck\n\n## BACKED UP 備份\n- Body\n", {1: "s6"})
    assert title_of(plan, 1).box is None


def test_c44_grouped_title_keeps_sibling():
    data, _, plan, out = run("# Deck\n\n## GROUPED TITLE 群組\n- Body\n", {1: "s7"})
    t = title_of(plan, 1)
    assert t.box is not None
    op = parts_of(out)
    assert boxes(tree_of(op[slides(op)[1]]))[702] == E(590, 84, 180, 180)
    assert look_diff(out, data) == []


def test_c44_pair_union_takes_cells():
    long = "本地送貨準時率由今年第一季開始逐步提升，目標係全年平均達到九十七"
    data, _, plan, out = run(f"# Deck\n\n## BESIDE THE PAIRS 旁邊\n- {long}\n- {long}\n", {1: "s8"})
    r = {bf.sid: bf for bf in plan.slides[1].boxes}
    assert r[811].role == "head" and r[812].role == "head"
    t = title_of(plan, 1)
    assert t.box is not None
    for h in (r[811].box, r[812].box):
        assert not hits(t.box, h), f"grown title {t.box} covers the pair union {h}"
    assert look_diff(out, data) == []


def test_c44_display_floor():
    assert display_floor(29700, SH) == 14850
    assert scaled(29700, 10, display_floor(29700, SH)) == 14850
    assert scaled(8000, 6) == 5600  # an 80 pt title keeps the 70% floor


def test_c44_c25_floor_rule():
    assert floor_ok("title", 29700, 14850, SH)
    assert not floor_ok("body", 2000, 1350, SH)
    assert not floor_ok("title", 8000, 5550, SH)
