"""C32 chips and backings (QA round 1 Q1) and C33 readability ranking (Q2 to Q4, precedence, small_text).

Expected picks and removals are written from the spec's QA round 1 section, never read from the planner."""

import io
import re
import zipfile

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.sample_plan import SMALL_TEXT, STEPS, build, needs
from sample_look import look_diff
from sample_oracle import A, nv_id, parts_of, slides, tree_of, walk
from test_c24_c27_sample_text import run


def _shapes(out: bytes, n: int) -> dict[int, object]:
    op = parts_of(out)
    return {nv_id(el)[0]: el for el in walk(tree_of(op[slides(op)[n - 1]]))}


def _text(el) -> str:
    return "".join(t.text or "" for t in el.iter("{%s}t" % A))


def _plan(fixture: str, text: str, overrides=None):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    return data, info, plan_deck(info, parse_outline(text), overrides, route="sample")


# --- C32: chips and backings ---------------------------------------------------------------------------------------


def test_c32_design_chip_and_6pct_box_go_10pct_panel_stays_empty():
    data, out = run("sample-design.pptx", "design", None)
    ids = _shapes(out, 4)  # Compare, on s4
    assert 431 not in ids  # the filled label chip
    assert 441 not in ids  # the filled 6% box that held cleared sample text
    assert 451 in ids and _text(ids[451]) == ""  # the filled 10% panel stays, as an empty shape
    assert look_diff(out, data) == []


def test_c32_design_backings_of_fragments_and_labels_go_with_their_groups():
    data, out = run("sample-design.pptx", "design", None)
    ids = _shapes(out, 1)  # the title slide, on s1
    for gone in (120, 121, 130, 131, 140, 141, 150, 151, 160, 161, 170, 171, 180, 181):
        assert gone not in ids, gone
    assert 111 in ids and 112 in ids  # the title destination's own white block stays behind it
    assert _text(ids[112]) == "Annual PlanOperations team"


def test_c32_marco_slide6_structure_backings_under_labels():
    data, info, plan = _plan("sample-backings.pptx", "## Health\n- One\n- Two\n")
    assert plan.slides[0].boxes[1].sid == 141  # both bullets into the largest body box
    out = fill(data, "sample-backings.pptx", plan)
    ids = _shapes(out, 1)
    for gone in (111, 112, 113, 121, 122, 123, 124, 142, 143, 144):  # small backings, labels, unused captions
        assert gone not in ids, gone
    assert 114 in ids  # the 9% backing under 11 stays (8% or more)
    assert 131 in ids  # the backing behind the destination that kept its text stays
    assert look_diff(out, data) == []


def _edit(data: bytes, name: str, fn) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in zin.infolist():
            b = zin.read(item.filename)
            z.writestr(item.filename, fn(b) if item.filename == name else b)
    return buf.getvalue()


def test_c32_rotated_slots_are_never_slot_destinations():
    """s2's 3-slot row with its first slot's group rotated: three bullets go to the largest body box instead."""
    data = (FIX / "sample-design.pptx").read_bytes()
    rotated = _edit(data, "ppt/slides/slide2.xml", lambda b: re.sub(
        rb'(<p:cNvPr id="210".*?<a:xfrm)>', rb'\1 rot="5400000">', b, count=1, flags=re.S))
    assert rotated != data
    text = "## Three\n- a\n- b\n- c\n"
    plain = plan_deck(read_template(data, "d.pptx"), parse_outline(text), {0: "s2"}, route="sample")
    assert [b.role for b in plain.slides[0].boxes] == ["title", "slot", "slot", "slot"]
    turned = plan_deck(read_template(rotated, "r.pptx"), parse_outline(text), {0: "s2"}, route="sample")
    assert "slot" not in [b.role for b in turned.slides[0].boxes]


# --- C33: readability ranking --------------------------------------------------------------------------------------


READ = "# Big cover\n\n## A\n- x\n\n## B\n- y\n\n## Part\n"


def test_c33_fitting_8pt_body_loses_to_18pt_body():
    _, _, plan = _plan("sample-readable.pptx", READ)
    assert plan.chosen[1] == "s3"  # s2's 8 pt body fits but is under 2%; s3's 18 pt body meets it
    assert SMALL_TEXT not in plan.slides[1].flags


def test_c33_14pt_title_sample_loses_the_title_slide_to_a_60pt_content_sample():
    _, _, plan = _plan("sample-readable.pptx", READ)
    assert plan.chosen[0] in ("s2", "s3")  # a content sample with a 60 pt title, not the 14 pt title sample s1
    assert SMALL_TEXT not in plan.slides[0].flags
    assert plan.chosen[3] != "s1"  # the section slide leaves s1 too


def test_c33_slot_group_with_one_slot_too_small_is_not_a_destination():
    _, _, plan = _plan("sample-readable.pptx", "## Three\n- a\n- b\n- c\n", {0: "s4"})
    roles = [(b.sid, b.role) for b in plan.slides[0].boxes]
    assert roles == [(401, "title"), (421, "body")]  # into the largest body box, not the slots


def test_c33_readable_previous_sample_beats_unreadable_unused_one():
    """B's only readable candidate is s3, which A used: variety relaxes to repeats inside the readable pool."""
    _, _, plan = _plan("sample-readable.pptx", READ)
    assert plan.chosen[1:3] == ("s3", "s3")


def test_c33_every_title_under_the_bar_fills_with_small_text():
    data, _, plan = _plan("sample-small.pptx", "# Cover\n\n## A\n- x\n\n## B\n- y\n")
    for s in plan.slides:
        assert SMALL_TEXT in s.flags
    fill(data, "sample-small.pptx", plan)  # the plan still fills


def test_c33_user_pick_below_the_bar_is_kept_with_small_text():
    _, _, plan = _plan("sample-readable.pptx", READ, {1: "s2"})
    assert plan.chosen[1] == "s2"
    assert SMALL_TEXT in plan.slides[1].flags
    assert SMALL_TEXT not in plan.slides[2].flags


def test_c33_q4_fewest_continuation_slides_decides_between_splitting_candidates():
    text = ("## Many\n- Short point one\n- Short point two\n- Short point three\n- Short point four\n"
            "- Short point five\n- This last bullet is a good deal longer than all the others here\n")
    _, info, plan = _plan("sample-split.pptx", text)
    p1, p2 = info.samples[0], info.samples[1]
    s = parse_outline(text).slides[0]
    b1, b2 = build(p1, s), build(p2, s)
    assert (len(b1.parts), len(b2.parts)) == (6, 4)
    assert STEPS < max(needs(p1, s)) < max(needs(p2, s))  # p1's text runs less far over its floor (rev 8 picked p1)
    assert plan.chosen == ("s2",)
    assert len(plan.slides) == 4
