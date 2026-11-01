"""QA round 2 checks: C34 grown box (R3 with its own backing), C35 order (R1, R2, R7), C36 backings by geometry (R5),
C37 route default (R4). Expected outcomes are written from the spec's QA round 2 section, never read from the planner."""

import pytest
from lxml import etree

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.sample_plan import GROWN, build, grow_build, largest_rect, slots_for
from sample_look import _canon, boxes, look_diff, shapes
from sample_oracle import A, P, parts_of, slides, tree_of

LONG = ("Quarter one: pilot the scheduling tool", "Quarter two: roll it out to every truck",
        "Quarter three: open the cross-border routes", "Quarter four: review and plan next year")
FOUR = "## Health\n" + "".join(f"- {t}\n" for t in LONG)
SIX = "## Plus\n" + "".join(f"- {t} and more words here\n" for t in LONG + LONG[:2])
C = 190500  # one cell of the R3 grid on the fixtures' 12192000 x 6858000 slide


def cells(c0, r0, c1, r1):
    return c0 * C, r0 * C, (c1 - c0 + 1) * C, (r1 - r0 + 1) * C


def grow(k: int, text: str = FOUR):
    data = (FIX / "sample-grow.pptx").read_bytes()
    info = read_template(data, "sample-grow.pptx")
    plan = plan_deck(info, parse_outline(text), {0: f"s{k}"}, route="sample")
    return data, info, plan, fill(data, "sample-grow.pptx", plan)


def out_boxes(out, n=1):
    op = parts_of(out)
    t = tree_of(op[slides(op)[n - 1]])
    return boxes(t), shapes(t)


def overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# --- C34 grown box --------------------------------------------------------------------------------------------------


def test_c34_marco_slide6_four_bullets_on_one_slide_in_a_grown_box():
    data, info, plan, out = grow(1)
    assert len(plan.slides) == 1 and GROWN in plan.slides[0].flags
    body = plan.slides[0].boxes[1]
    assert body.sid == 131 and body.box is not None and len(body.paras) == 4
    ob, sh = out_boxes(out)
    assert ob[131] == body.box
    for gone in (111, 112, 113, 114, 121, 122, 123, 124, 132, 133, 134):  # backings, labels, other captions
        assert gone not in sh
    assert not overlaps(ob[131], ob[141])  # the kept photo
    title = ob[101]
    pad = 0.02 * 12192000
    assert not overlaps(ob[131], (title[0] - pad, title[1] - pad, title[2] + 2 * pad, title[3] + 2 * pad))
    assert look_diff(out, data) == []  # C23: only the declared growth; the grown box on free cells of its own grid


def test_c34_grown_box_keeps_its_shape_id_and_properties_apart_from_xfrm():
    data, _, _, out = grow(1)
    sp_, op = parts_of(data), parts_of(out)
    src = shapes(tree_of(sp_[slides(sp_)[0]]))[131]
    dst = shapes(tree_of(op[slides(op)[0]]))[131]

    def props(el):
        pr = etree.fromstring(etree.tostring(el.find("{%s}spPr" % P)))
        for x in pr.findall("{%s}xfrm" % A):
            pr.remove(x)
        tx = el.find("{%s}txBody" % P)
        return _canon(pr), _canon(tx.find("{%s}bodyPr" % A)), _canon(tx.find("{%s}lstStyle" % A))
    assert props(src) == props(dst)


def test_c34_declared_background_takes_no_cells():
    data, _, plan, out = grow(2)
    assert len(plan.slides) == 1 and GROWN in plan.slides[0].flags
    ob, _ = out_boxes(out)
    assert overlaps(ob[221], ob[201]) and ob[221][2] * ob[221][3] > 0.5 * ob[201][2] * ob[201][3]
    assert look_diff(out, data) == []


def test_c34_free_area_under_25_by_15_is_not_used():
    _, info, plan, _ = grow(3)
    assert GROWN not in plan.slides[0].flags and len(plan.slides) == 4
    assert grow_build(info.samples[2], parse_outline(FOUR).slides[0]) is None


def test_c34_slot_groups_and_two_column_slides_never_grow():
    info = read_template((FIX / "sample-design.pptx").read_bytes(), "sample-design.pptx")
    long = " and a good many more words to fill the box"
    two = parse_outline("## Cols\n" + "".join(f"- left {i}{long}\n" for i in range(6)) + "||\n"
                        + "".join(f"- right {i}{long}\n" for i in range(6))).slides[0]
    assert grow_build(info.samples[3], two) is None  # s4, the two-column sample
    slots = parse_outline("## Three\n- a\n- b\n- c\n").slides[0]
    assert slots_for(info.samples[1], slots.columns[0]) is not None and grow_build(info.samples[1], slots) is None


def test_c34_equal_area_ties_go_top_most():
    data, _, plan, out = grow(4, SIX)
    assert plan.slides[0].boxes[1].box == cells(24, 8, 39, 25)  # the vertical bar, not the horizontal one
    assert look_diff(out, data) == []


def test_c34_equal_area_ties_then_left_most():
    W, H = 20, 12
    taken = [[True] * W for _ in range(H)]
    for r in range(4, 8):  # two free 4 by 6 areas side by side around a 2 by 2 need in the middle, same top
        for c in range(4, 16):
            taken[r][c] = False
    taken[4][4] = taken[4][15] = False
    for r in range(4, 8):
        taken[r][9] = taken[r][10] = False
    assert largest_rect(taken, (5, 6, 9, 10)) == (4, 7, 4, 15)
    # left-most among equal areas with the same top: block one column on each side so both 4 x 5 runs tie
    for r in range(4, 8):
        taken[r][4] = True
    taken2 = [row[:] for row in taken]
    for r in range(4, 8):
        taken2[r][15] = True
        taken2[r][12] = True  # right run now cols 11..11, left run 5..10
    assert largest_rect(taken2, (5, 6, 9, 10)) == (4, 7, 5, 11)


def test_c34_grouped_body_grows_with_its_backing_and_groups_siblings_fixed():
    data, _, plan, out = grow(5, SIX)
    body = plan.slides[0].boxes[1]
    assert len(plan.slides) == 1 and body.backing and body.backing[0] == 511
    sb = boxes(tree_of(parts_of(data)[slides(parts_of(data))[4]]))
    ob, _ = out_boxes(out)
    assert ob[513] == sb[513]  # the side accent keeps its slide-space box exactly
    margins = lambda bx: (bx[512][0] - bx[511][0], bx[512][1] - bx[511][1],
                          bx[511][0] + bx[511][2] - bx[512][0] - bx[512][2], bx[511][1] + bx[511][3] - bx[512][1] - bx[512][3])
    assert all(abs(u - v) <= 12 for u, v in zip(margins(ob), margins(sb)))  # the backing keeps its margins
    assert ob[510][2] > sb[510][2] and ob[510][3] > sb[510][3]  # the group grew to hold both
    assert look_diff(out, data) == []


def test_c34_positive_margin_backing_beside_an_obstacle():
    data, _, plan, out = grow(6)
    body = plan.slides[0].boxes[1]
    assert GROWN in plan.slides[0].flags and body.backing[0] == 611
    ob, _ = out_boxes(out)
    assert not overlaps(ob[611], ob[621]) and not overlaps(ob[612], ob[621])  # the obstacle stays uncovered
    assert look_diff(out, data) == []


def test_c34_body_under_two_qualifying_backings_does_not_grow():
    _, info, plan, _ = grow(7)
    assert GROWN not in plan.slides[0].flags
    assert grow_build(info.samples[6], parse_outline(FOUR).slides[0]) is None


# --- C35 order ------------------------------------------------------------------------------------------------------


def order_plan(text, overrides=None):
    data = (FIX / "sample-order.pptx").read_bytes()
    info = read_template(data, "sample-order.pptx")
    return info, plan_deck(info, parse_outline(text), overrides, route="sample")


def test_c35_variety_never_adds_a_slide():
    """Six two-line bullets fit on one slide only on o1's tall body; every other sample splits them. B repeats o1
    rather than take a split for variety."""
    words = "point {i} with a fairly long run of words that wraps past the width of the box onto a second line here"
    six = "".join("- " + words.format(i=i) + "\n" for i in range(6))
    info, plan = order_plan(f"## A\n{six}\n## B\n{six}")
    assert plan.chosen[:2] == ("s1", "s1")
    assert [s.source for s in plan.slides] == [0, 1]
    s = parse_outline(f"## B\n{six}").slides[0]
    assert all(len(build(x, s).parts) > 1 for x in info.samples[1:])  # any other pick would add a slide


def test_c35_continuation_drops_its_suffix_only_when_the_suffix_alone_overflows():
    eight = "".join(f"- point {i}\n" for i in range(8))
    _, narrow = order_plan(f"## 時間表\n{eight}", {0: "s4"})
    assert [s.title for s in narrow.slides] == ["時間表", "時間表"]
    _, wide = order_plan(f"## 時間表\n{eight}", {0: "s1"})
    assert [s.title for s in wide.slides] == ["時間表", "時間表（續）"]


def test_c35_overflowing_one_slide_slots_lose_to_a_fitting_body():
    info, plan = order_plan("## Three\n- " + "\n- ".join(f"a rather long slot text number {i} here" for i in range(3)) + "\n")
    o3 = info.samples[2]
    s = parse_outline("## Three\n- " + "\n- ".join(f"a rather long slot text number {i} here" for i in range(3)) + "\n").slides[0]
    assert slots_for(o3, s.columns[0]) is None  # R7: a slot that would be warned disqualifies its group
    assert "slot" not in [b.role for b in build(o3, s).parts[0].boxes]
    assert plan.chosen[0] != "s3"


# --- C36 backings by geometry ---------------------------------------------------------------------------------------


def test_c36_backings_by_geometry():
    data = (FIX / "sample-geom.pptx").read_bytes()
    info = read_template(data, "sample-geom.pptx")
    out = fill(data, "sample-geom.pptx", plan_deck(info, parse_outline("## Backings\n- one\n- two\n"), {0: "s1"}, route="sample"))
    _, sh = out_boxes(out)
    assert 111 in sh  # a curved leaf path over a label stays
    assert 112 not in sh  # a rect preset backing goes
    assert 113 not in sh  # a four-corner rectangle path (Marco's slide 6 backings) goes
    assert 114 in sh  # a rotated picture-filled rectangle (Marco's olive leaf) is not a backing and stays
    assert look_diff(out, data) == []


# --- C37 route default ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fixture,routes,route", [
    ("sample-thin.pptx", ("sample", "layout"), "layout"),
    ("sample-two.pptx", ("sample", "layout"), "layout"),
    ("sample-only2.pptx", ("sample",), "sample"),
    ("layout-design.pptx", ("sample", "layout"), "layout"),
    ("layout-photos.pptx", ("sample", "layout"), "layout"),
    ("sample-design.pptx", ("sample", "layout"), "sample"),
])
def test_c37_route_default(fixture, routes, route):
    info = read_template((FIX / fixture).read_bytes(), fixture)
    assert info.routes == routes and info.route == route
