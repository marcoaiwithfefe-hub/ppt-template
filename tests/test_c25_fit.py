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
from rev9_oracle import any_chinese
from sample_oracle import nv_id, parts_of, resolved_paras, slides, tree_of, walk

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def floor_of(eff):
    return (eff * 70 + 4999) // 5000 * 50


def floor_for(role, eff, slide_h):
    """Rev 9 T6: a title whose effective size is at or above 12% of the slide height (three times Q2's bar) floors at
    50% of it, rounded up to the 50 grid, never under Q2's bar (4% of the slide height, rounded up to the grid);
    every other box at 70%."""
    if role == "title" and eff * 12700 >= 12 * slide_h:
        bar = -(-4 * slide_h // 12700)
        return max((eff * 50 + 4999) // 5000 * 50, -(-bar // 50) * 50)
    return floor_of(eff)


def floor_ok(role, eff, written, slide_h) -> bool:
    return written % 50 == 0 and written >= floor_for(role, eff, slide_h)


def plan_on(fixture, text, overrides=None):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    plan = plan_deck(info, parse_outline(text), overrides, route="sample")
    return data, info, plan


def written_sizes(out: bytes) -> dict[tuple[int, int], list[list[int | None]]]:
    """(slide, shape id) -> per paragraph holding runs, the sz written on each of its runs (None where no size is
    written). Codex rev 9 round 1: T1 cuts a paragraph into several runs, so sizes are compared per paragraph."""
    op = parts_of(out)
    res = {}
    for n, name in enumerate(slides(op), start=1):
        for el in walk(tree_of(op[name])):
            sid, _ = nv_id(el)
            paras = []
            for par in el.iter(A + "p"):
                rs = [r.find(A + "rPr") for r in par.iter(A + "r")]
                if rs:
                    paras.append([int(r.get("sz")) if r is not None and r.get("sz") else None for r in rs])
            res[(n, sid)] = paras
    return res


def t2_line(spec, size, text):
    """Rev 9 T2 (C40 extends C25 to line spacing): spcPts scaled by the written size over the level's effective size,
    floored to a hundredth of a point, at least 1.1 times the size on a paragraph holding Chinese; spcPct below 90%
    raised to 90% on a Chinese paragraph."""
    kind, val = spec.ln
    zh = any_chinese(text)
    if kind == "pts":
        w = round(val / 127) * size // spec.size
        if zh:
            w = max(w, -(-11 * size // 10))
        return ("pts", w * 12700 / 100)
    if kind == "pct" and zh and val < 0.9:
        return ("pct", 0.9)
    return spec.ln


def check_resolved(n, bf, sb, op, name, shapes_by_id):
    """Code review F6: each written paragraph's size, line spacing, spacing before and after and left margin, resolved
    on the output by the test-side oracle (run, paragraph, the box's list style, its inheritance), equal the values the
    estimate used: the plan's written size or the box's effective size, and the box's level spacing."""
    got = resolved_paras(op, name, shapes_by_id[bf.sid])
    want = []
    for lvl, text in bf.paras:
        spec = sb.lvl1 if lvl == 1 else sb.lvl2
        size = bf.sizes[lvl - 1] or spec.size
        want.append((lvl, size, t2_line(spec, size, text), spec.bef, spec.aft, spec.margin))
    assert got == want, f"slide {n} box {bf.sid}: resolved {got}, estimate used {want}"


def check_plan(info, plan, out):
    """The generic C25 checks over every box of every output slide."""
    samples = {s.id: s for s in info.samples}
    sizes = written_sizes(out)
    op = parts_of(out)
    names = slides(op)
    for n, ps in enumerate(plan.slides, start=1):
        S = samples[ps.layout]
        by_id = {nv_id(el)[0]: el for el in walk(tree_of(op[names[n - 1]]))}
        for bf in ps.boxes:
            if bf.role in ("echo", "label"):
                continue  # rev 9: echoes and number labels carry no fit estimate (T3, T5)
            sb = S.box(bf.sid)
            check_resolved(n, bf, sb, op, names[n - 1], by_id)
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
                assert bf.sizes[0] == floor_for(bf.role, sb.lvl1.size, S.slide[1])
            got = sizes[(n, bf.sid)]
            if bf.sizes == (0, 0):
                assert all(g is None or g == sb.lvl1.size for par in got for g in par)
            else:
                want = [bf.sizes[0] if lvl == 1 else bf.sizes[1] for lvl, _ in bf.paras]
                assert len(got) == len(want) and all(all(g == w for g in par) for par, w in zip(got, want)), (
                    f"slide {n} box {bf.sid}: written {got}, estimate used {want} (every run of a paragraph)")
                for w, lvl in zip(want, [lvl for lvl, _ in bf.paras]):
                    eff = sb.lvl1.size if lvl == 1 else sb.lvl2.size
                    assert floor_ok(bf.role, eff, w, S.slide[1]), f"size {w} off the grid or under the floor of {eff}"


def test_c25_generic_on_every_fit_case():
    cases = [
        ("sample-fit.pptx", "# A much longer deck title than the box\nA subtitle that runs on past its small box\n\n## Short\n- one\n"),
        ("sample-fit.pptx", "## Many\n" + "".join(f"- bullet number {i} with some words\n" for i in range(6))),
        ("sample-fit.pptx", "## Slots\n- a fairly long first slot text\n- second\n- third\n"),
        ("sample-design.pptx", open(FIX.parent.parent / "tests/outlines/sample/design.md", encoding="utf-8").read()),
        ("sample-rotated.pptx", "## Turn\n- spin\n"),
        ("sample-fit.pptx", "## Two levels\n- one\n  - sub one\n- two\n"),
        ("sample-biglvl2.pptx", "## Two levels\n- one\n  - sub one\n"),
        # Codex rev 9 round 1: a mixed-script title in a Latin-only face (T1 cuts it into runs) that shrinks
        ("sample-latin-font.pptx", MIXED),
    ]
    for fixture, text in cases:
        data, info, plan = plan_on(fixture, text)
        check_plan(info, plan, fill(data, fixture, plan))
    for k in (1, 2, 3):  # code review F6: inherited sizes and spacing, level 2 included, on each sample
        data, info, plan = plan_on("sample-inherit.pptx", INHERIT, {0: f"s{k}"})
        check_plan(info, plan, fill(data, "sample-inherit.pptx", plan))


INHERIT = "## Inherit\n- one\n  - sub one\n- two\n"
MIXED = ("# 匯通物流 Logistics 2027 年度計劃 Annual Plan Review 全面檢討 Summit\nStrategic consulting 策略顧問 for "
         "logistics 物流 teams across Hong Kong 香港 and the Greater Bay Area 大灣區 with annual planning 年度計劃 support "
         "and quarterly 季度 reviews for every regional 區域 office\n")


def test_c25_mixed_script_case_is_split_and_shrunk():
    """The MIXED case above exercises the per-paragraph comparison: its 12 pt Montserrat subtitle is shrunk and each
    paragraph is written as several runs (T1)."""
    data, info, plan = plan_on("sample-latin-font.pptx", MIXED)
    t = next(bf for bf in plan.slides[0].boxes if bf.role == "subtitle")
    assert t.status == SHRUNK
    got = written_sizes(fill(data, "sample-latin-font.pptx", plan))[(1, t.sid)]
    assert len(got) == 1 and len(got[0]) > 1 and set(got[0]) == {t.sizes[0]}


def test_c25_inherited_sizes_resolve_on_the_output():
    """Written by hand from the fixture (make_sample_inherit) and python-pptx's default master and presentation: no
    written run carries a size, so each resolves through the box's inheritance."""
    want = {1: (111, [2400, 2800, 2400]), 2: (211, [1800, 1800, 1800]), 3: (311, [2000, 2000, 2000])}
    for k, (sid, sizes) in want.items():
        data, info, plan = plan_on("sample-inherit.pptx", INHERIT, {0: f"s{k}"})
        out = fill(data, "sample-inherit.pptx", plan)
        op = parts_of(out)
        name = slides(op)[0]
        el = next(e for e in walk(tree_of(op[name])) if nv_id(e)[0] == sid)
        got = resolved_paras(op, name, el)
        assert [g[1] for g in got] == sizes and [g[0] for g in got] == [1, 2, 1]
        if k == 1:
            assert got[0][2] == ("pct", 0.9) and got[0][3] == ("pct", 0.2) and got[1][5] == 742950
        if k == 3:
            assert got[1][3] == ("pts", 76200.0) and got[1][5] == 600000


# rev 9 T6 grows a title into the free space beside and below it, so the overflowing title here runs too long for
# any grown box as well (four times the rev 8 text): the title still carries its own warning at the 70% floor
LONG_TITLE = " ".join(["A title far too long for this very narrow box"] * 4)


def test_c25_title_shrinks_then_warns():
    _, info, plan = plan_on("sample-fit.pptx", "## Mid length title\n- x\n", {0: "s4"})
    t = plan.slides[0].boxes[0]
    assert t.role == "title" and (t.status in ("shrunk", "warned") or t.box is not None)  # rev 9 T6 may grow it
    _, info, plan = plan_on("sample-fit.pptx", f"## {LONG_TITLE}\n- x\n", {0: "s4"})
    t = plan.slides[0].boxes[0]
    assert t.status == "warned" and t.sizes[0] == floor_of(4000)
    assert "fit_warn" in [w.code for w in plan.warnings]


def test_c25_subtitle_shrinks():
    _, info, plan = plan_on("sample-fit.pptx", "# T\nA subtitle that is longer than its box\n\n## S\n- x\n", {0: "s1"})
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
    text = f"## {LONG_TITLE}\n" + "".join(f"- point {i}\n" for i in range(8))
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
    assert written_sizes(out)[(1, 411)] == [[2000]]  # the donor's own size, copied unchanged


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
