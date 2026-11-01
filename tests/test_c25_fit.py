"""C25 fit on the sample route (story 31): every emitted modelled box fits by the estimate after shrinking, or carries
its own fit warning; check-this-slide only on unmodelled boxes; a split never excuses a box that still overflows;
every size the fill wrote is on the 50 grid, at or above its 70% floor, and equals the size the estimate used;
untouched text keeps its resolved effective size. Titles, subtitles, single long bullets, slot boxes, the rotated
box and a split body under an overflowing title are tested apart; sample-design's split title lands in one widened
box with the other fragments and labels gone."""

import io
import zipfile

from lxml import etree

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.outline import Item
from deckfill.plan import height
from deckfill.sample_plan import SHRUNK, scaled
from sample_oracle import nv_id, parts_of, slides, tree_of, walk

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def floor_of(eff):
    return (eff * 70 + 4999) // 5000 * 50


def plan_on(fixture, text, overrides=None):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    plan = plan_deck(info, parse_outline(text), overrides, route="sample")
    return data, info, plan


def written_sizes(out: bytes) -> dict[tuple[int, int], list[int]]:
    """(slide, shape id) -> the sz written on each run of that box (None where no size is written)."""
    op = parts_of(out)
    res = {}
    for n, name in enumerate(slides(op), start=1):
        for el in walk(tree_of(op[name])):
            sid, _ = nv_id(el)
            szs = [r.find(A + "rPr").get("sz") if r.find(A + "rPr") is not None else None for r in el.iter(A + "r")]
            res[(n, sid)] = [int(s) if s else None for s in szs]
    return res


def check_plan(info, plan, out):
    """The generic C25 checks over every box of every output slide."""
    samples = {s.id: s for s in info.samples}
    sizes = written_sizes(out)
    for n, ps in enumerate(plan.slides, start=1):
        S = samples[ps.layout]
        for bf in ps.boxes:
            sb = S.box(bf.sid)
            if bf.status == "check":
                assert sb.unmodelled, f"slide {n} box {bf.sid}: check on a box the estimate models"
                continue
            assert not sb.unmodelled, f"slide {n} box {bf.sid}: an unmodelled box got status {bf.status}"
            items = tuple(Item(lvl, t) for lvl, t in bf.paras)
            s1 = bf.sizes[0] or sb.lvl1.size
            s2 = bf.sizes[1] or sb.lvl2.size
            f = sb.fit_at(bf.box, s1, s2)
            fits = height(items, f) <= f.height
            if bf.status in ("fits", SHRUNK):
                assert fits, f"slide {n} box {bf.sid}: status {bf.status} but the estimate overflows"
            else:
                assert bf.status == "warned" and not fits
                assert bf.sizes[0] == floor_of(sb.lvl1.size)
            got = sizes[(n, bf.sid)]
            if bf.sizes == (0, 0):
                assert all(g == (sb.lvl1.size if sb.lvl1.size else None) or g is None or g == sb.lvl1.size for g in got)
            else:
                want = [bf.sizes[0] if lvl == 1 else bf.sizes[1] for lvl, _ in bf.paras]
                assert got == want, f"slide {n} box {bf.sid}: written {got}, estimate used {want}"
                for w, lvl in zip(want, [lvl for lvl, _ in bf.paras]):
                    eff = sb.lvl1.size if lvl == 1 else sb.lvl2.size
                    assert w % 50 == 0 and w >= floor_of(eff), f"size {w} off the grid or under the floor of {eff}"


def test_c25_generic_on_every_fit_case():
    cases = [
        ("sample-fit.pptx", "# A much longer deck title than the box\nA subtitle that runs on past its small box\n\n## Short\n- one\n"),
        ("sample-fit.pptx", "## Many\n" + "".join(f"- bullet number {i} with some words\n" for i in range(6))),
        ("sample-fit.pptx", "## Slots\n- a fairly long first slot text\n- second\n- third\n"),
        ("sample-design.pptx", open(FIX.parent.parent / "tests/outlines/sample/design.md", encoding="utf-8").read()),
        ("sample-rotated.pptx", "## Turn\n- spin\n"),
    ]
    for fixture, text in cases:
        data, info, plan = plan_on(fixture, text)
        check_plan(info, plan, fill(data, fixture, plan))


def test_c25_title_shrinks_then_warns():
    _, info, plan = plan_on("sample-fit.pptx", "## Mid length title\n- x\n", {0: "s4"})
    t = plan.slides[0].boxes[0]
    assert t.role == "title" and t.status in ("shrunk", "warned")
    _, info, plan = plan_on("sample-fit.pptx", "## A title far too long for this very narrow box\n- x\n", {0: "s4"})
    t = plan.slides[0].boxes[0]
    assert t.status == "warned" and t.sizes[0] == floor_of(4000)
    assert "fit_warn" in [w.code for w in plan.warnings]


def test_c25_subtitle_shrinks():
    _, info, plan = plan_on("sample-fit.pptx", "# T\nA subtitle that is longer than its box\n\n## S\n- x\n")
    sub = next(b for b in plan.slides[0].boxes if b.role == "subtitle")
    assert sub.status in ("shrunk", "warned")


def test_c25_single_long_bullet_warns_without_split():
    long = "word " * 120
    _, info, plan = plan_on("sample-fit.pptx", f"## One\n- {long.strip()}\n", {0: "s2"})
    parts = [s for s in plan.slides if s.source == 0]
    assert len(parts) == 1
    body = next(b for b in parts[0].boxes if b.role == "body")
    assert body.status == "warned" and "warned" in parts[0].flags


def test_c25_slot_box_shrinks_alone():
    _, info, plan = plan_on("sample-fit.pptx", "## Slots\n- a fairly long first slot text here\n- b\n- c\n", {0: "s3"})
    slots = [b for b in plan.slides[0].boxes if b.role == "slot"]
    assert [b.sid for b in slots] == [311, 312, 313]
    assert slots[0].status in ("shrunk", "warned") and slots[1].status == "fits" and slots[1].sizes == (0, 0)


def test_c25_rotated_box_is_check_only():
    _, info, plan = plan_on("sample-rotated.pptx", "## Turn\n- spin\n")
    body = next(b for b in plan.slides[0].boxes if b.role == "body")
    assert body.status == "check" and body.sizes == (0, 0)
    assert plan.slides[0].flags == ("check",)


def test_c25_split_body_with_an_overflowing_title_carries_both():
    text = "## A title far too long for this very narrow box\n" + "".join(f"- point {i}\n" for i in range(8))
    _, info, plan = plan_on("sample-fit.pptx", text, {0: "s4"})
    parts = [s for s in plan.slides if s.source == 0]
    assert len(parts) == 2
    for ps in parts:
        assert "split" in ps.flags and "warned" in ps.flags
        title = ps.boxes[0]
        assert title.status == "warned"  # the split does not excuse the title
        body = next(b for b in ps.boxes if b.role == "body")
        assert body.status in ("fits", "shrunk")


def test_c25_untouched_text_keeps_its_effective_size():
    data, info, plan = plan_on("sample-fit.pptx", "## Short\n- one\n", {0: "s4"})
    out = fill(data, "sample-fit.pptx", plan)
    body = next(b for b in plan.slides[0].boxes if b.role == "body")
    assert body.status == "fits" and body.sizes == (0, 0)
    assert written_sizes(out)[(1, 411)] == [2000]  # the donor's own size, copied unchanged


def test_c25_split_title_lands_in_one_widened_box():
    data, info, plan = plan_on("sample-design.pptx", "# Annual Plan\n\n## A\n- x\n")
    out = fill(data, "sample-design.pptx", plan)
    op = parts_of(out)
    tree = tree_of(op[slides(op)[0]])
    ids = {nv_id(el)[0]: el for el in walk(tree)}
    for gone in (122, 132, 142, 152, 162, 172, 182):  # the other fragments and the labels (text boxes without fill)
        assert gone not in ids
    s1 = info.samples[0]
    assert plan.slides[0].boxes[0].box == s1.title_box  # the destination widened to the union of the fragments
    assert "".join(t.text for t in ids[112].iter(A + "t")) == "Annual Plan"
