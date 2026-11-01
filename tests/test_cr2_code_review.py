"""Code review round 2 fixes (rev 8, fix-cr2). Expected outcomes are written from the review's findings and the
fixtures' hand-worked geometry, never read from the planner.

N1: Q1 clearing and its backing test measure shapes and destinations by their drawn slide-space bounds (rotation and
flips through every enclosing group), in production and in the C23 comparator.
"""

import pytest
from lxml import etree

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.package import check_integrity, load
from sample_look import look_diff
from sample_oracle import P, parts_of, slides, tree_of

ONE = "## A\n- one\n"
# k: (chip drawn behind the body, which stays as its backing; chip stored behind it but drawn elsewhere, which goes)
CHIPS = {1: (121, 122), 2: (221, 222)}


def chips(k):
    data = (FIX / "sample-flipchip.pptx").read_bytes()
    info = read_template(data, "sample-flipchip.pptx")
    plan = plan_deck(info, parse_outline(ONE), {0: f"s{k}"}, route="sample")
    return data, plan, fill(data, "sample-flipchip.pptx", plan)


def out_shapes(out):
    op = parts_of(out)
    tree = tree_of(op[slides(op)[0]])
    found = {}
    for el in tree.iter("{%s}sp" % P):
        c = el.find(".//{%s}cNvPr" % P)
        found[int(c.get("id"))] = el
    return op, tree, found


@pytest.mark.parametrize("k", [1, 2], ids=["flipped", "rotated"])
def test_n1_chip_drawn_behind_the_kept_body_stays_as_its_backing(k):
    _, plan, out = chips(k)
    assert [b.sid for b in plan.slides[0].boxes] == [k * 100 + 1, k * 100 + 11]
    _, _, found = out_shapes(out)
    behind, elsewhere = CHIPS[k]
    assert behind in found, "the chip drawn behind the body was removed"
    assert "".join(t.text or "" for t in found[behind].iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t")) == ""


@pytest.mark.parametrize("k", [1, 2], ids=["flipped", "rotated"])
def test_n1_chip_drawn_elsewhere_goes(k):
    _, _, out = chips(k)
    _, _, found = out_shapes(out)
    assert CHIPS[k][1] not in found, "the chip drawn away from the body was kept"
    assert check_integrity(load(out, "out.pptx").parts) == []


@pytest.mark.parametrize("k", [1, 2], ids=["flipped", "rotated"])
def test_n1_comparator_agrees_and_rejects_removing_the_backing(k):
    data, _, out = chips(k)
    assert look_diff(out, data) == []
    # the same output with the backing chip removed: C23 must name it
    op, tree, found = out_shapes(out)
    behind = found[CHIPS[k][0]]
    behind.getparent().remove(behind)
    name = slides(op)[0]
    op[name] = etree.tostring(tree.getroottree().getroot(), xml_declaration=True, encoding="UTF-8", standalone=True)
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in op.items():
            z.writestr(n, b)
    diffs = look_diff(buf.getvalue(), data)
    assert any(f"shape {CHIPS[k][0]} " in d and "missing" in d for d in diffs), diffs


# ------------------------------------------------------------------------------------------------------------ Edge 1

REFERENCE = (FIX.parent / "reference-outline.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("fixture", ["sample-badidx.pptx", "sample-badidx2.pptx"])
@pytest.mark.parametrize("route", ["layout", "sample"])
def test_edge1_borrowed_footer_with_a_bad_idx_is_skipped(route, fixture):
    """sample-badidx: the only footer D4 step 1 can borrow has idx="bad" ("²" in sample-badidx2, round 3) and the new
    slides' layout has no footer box of its own, so placing it would read the idx. It is skipped on both routes; the
    decks fill."""
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    out = fill(data, fixture, plan_deck(info, parse_outline(REFERENCE), route=route))
    assert check_integrity(load(out, "out.pptx").parts) == []
    op = parts_of(out)
    for name in slides(op):
        for ph in etree.fromstring(op[name]).iter("{%s}ph" % P):
            assert ph.get("idx") is None or ph.get("idx").isascii() and ph.get("idx").isdigit(), f"{name}: idx {ph.get('idx')!r}"


# ------------------------------------------------------------------------------------------- round 3: footer checks

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _footer(idx=None, off=None, ext=None):
    xml = (f'<p:sp xmlns:p="{P}" xmlns:a="{A_NS}"><p:nvSpPr><p:cNvPr id="9" name="F"/><p:cNvSpPr/><p:nvPr>'
           f'<p:ph type="ftr"{"" if idx is None else f" idx={idx!r}"}/></p:nvPr></p:nvSpPr><p:spPr>')
    if off or ext:
        xml += "<a:xfrm>"
        xml += "" if off is None else f'<a:off x="{off[0]}" y="{off[1]}"/>'
        xml += "" if ext is None else f'<a:ext cx="{ext[0]}" cy="{ext[1]}"/>'
        xml += "</a:xfrm>"
    return etree.fromstring(xml + "</p:spPr></p:sp>")


@pytest.mark.parametrize("sp,ok", [
    (_footer(), True), (_footer("11"), True), (_footer("bad"), False), (_footer("²"), False),
    (_footer("11", (0, 6300000), (4000000, 300000)), True), (_footer("11", ("bad", 0)), False),
    (_footer("11", (0, 0), ("1.5", 300000)), False), (_footer("11", None, (4000000, "²")), False),
], ids=["none", "11", "bad", "superscript-two", "box", "off-bad", "ext-decimal", "ext-superscript"])
def test_round3_footer_ok_uses_int(sp, ok):
    from deckfill.template import footer_ok

    assert footer_ok(sp) is ok


@pytest.mark.parametrize("route", ["layout", "sample"])
def test_round3_footer_with_an_unreadable_box_is_skipped(route):
    """sample-footbad: the only footer to borrow has a:off x="bad". It is never copied on either route, so the decks
    carry no unreadable box."""
    data = (FIX / "sample-footbad.pptx").read_bytes()
    info = read_template(data, "sample-footbad.pptx")
    out = fill(data, "sample-footbad.pptx", plan_deck(info, parse_outline("## A\n- x\n\n## B\n- y\n"), route=route))
    op = parts_of(out)
    for name in slides(op):
        assert b'x="bad"' not in op[name]
    assert check_integrity(load(out, "out.pptx").parts) == []
