"""C26 (silent break: copies open clean), C29 (sample footers), C30 (limits on the sample route).

C26: the D4 integrity check passes on every sample-route output (the Open XML SDK validator runs on them in
qa/c5/run_c5.py); sample-jump's link is gone with its relationship; media only sample slides used survive when a copy
uses them and are dropped when none does, and every kept part is the template's own (the C3 kept-part oracle); the
chart sample is never copied; no connector names a removed shape.
C29: copies carry each footer type once, their own sample first; a fixed date stays text; a grouped footer is removed
and re-added once where D4 names a position, and not added where none exists; slide numbers renumbered.
C30: past the generated-XML, copied-shape or paragraph cap the planner refuses with too_big before any output tree is
built and without exhausting memory; the fill re-checks its running total."""

import io
import tracemalloc
import zipfile

import pytest
from lxml import etree

from conftest import FIX
from deckfill import TemplateError, fill, parse_outline, plan_deck, read_template
from deckfill import sample_fill, sample_plan
from deckfill.package import check_integrity
from oracle import kept_part_problems
from sample_oracle import nv_id, parts_of, rels, slides, tree_of, walk, xml
from test_c24_c27_sample_text import CASES, run

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
RT_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


@pytest.mark.parametrize("fixture,outline,overrides,gold", CASES, ids=[c[3] for c in CASES])
def test_c26_integrity_and_kept_parts(fixture, outline, overrides, gold):
    data, out = run(fixture, outline, overrides)
    op = parts_of(out)
    assert check_integrity(op) == []
    assert kept_part_problems(data, out) == []


def test_c26_slide_link_gone_with_its_relationship():
    data, out = run("sample-jump.pptx", "two-slides", None)
    op = parts_of(out)
    first = slides(op)[0]
    assert all(t != RT_SLIDE for t, _, _ in rels(op, first).values())
    assert not list(xml(op[first]).iter(A + "hlinkClick"))
    assert 121 in {nv_id(el)[0] for el in walk(tree_of(op[first]))}  # the shape stays, its link goes


def test_c26_media_follow_the_copies():
    data, out = run("sample-design.pptx", "design", None)
    sp, op = parts_of(data), parts_of(out)
    src_media = {n: b for n, b in sp.items() if n.startswith("ppt/media/")}
    out_media = {n: b for n, b in op.items() if n.startswith("ppt/media/")}
    used = {"ppt/slides/slide%d.xml" % k for k in (1, 2, 3, 4, 6)}  # the samples the golden copies
    def media_of(parts, name):
        return {t for (rt, t, ext) in rels(parts, name).values() if t.startswith("ppt/media/")}
    keep = set().union(*(media_of(sp, n) for n in used))
    unused = set().union(*(media_of(sp, f"ppt/slides/slide{k}.xml") for k in (5, 7, 8))) - keep
    assert keep and unused
    assert {sp[n] for n in keep} <= set(out_media.values())  # same bytes kept
    assert not ({sp[n] for n in unused} & set(out_media.values()))  # media no copy uses are gone
    assert len(src_media) > len(out_media)


def test_c26_chart_sample_never_copied():
    data, out = run("sample-chart.pptx", "two-slides", None)
    op = parts_of(out)
    assert not [n for n in op if n.startswith("ppt/charts/")]
    assert not [el for name in slides(op) for el in xml(op[name]).iter(P + "graphicFrame")]


def test_c26_connector_keeps_no_reference_to_a_removed_shape():
    data, out = run("sample-connector.pptx", "connector", None)
    op = parts_of(out)
    tree = tree_of(op[slides(op)[0]])
    ids = {nv_id(el)[0] for el in walk(tree)}
    assert 112 not in ids and 121 in ids
    for tag in ("stCxn", "endCxn"):
        for c in tree.iter(A + tag):
            assert int(c.get("id")) in ids


# --- C29


def footers_on(out):
    op = parts_of(out)
    res = []
    for name in slides(op):
        found = []
        for el in walk(tree_of(op[name])):
            nv = el.find(P + "nvSpPr")
            ph = None if nv is None else nv.find(P + "nvPr").find(P + "ph")
            if ph is not None and ph.get("type") in ("sldNum", "ftr", "dt"):
                top = el.getparent().tag == P + "spTree"
                fld = el.find(".//" + A + "fld") is not None
                text = "".join(t.text or "" for t in el.iter(A + "t"))
                found.append((ph.get("type"), text, top, fld))
        res.append(found)
    return res


def test_c29_footers_once_own_first_fixed_date_grouped_re_added():
    _, out = run("sample-footer.pptx", "footer", {1: "s1", 2: "s2", 3: "s3", 4: "s4"})
    for n, found in enumerate(footers_on(out), start=1):
        types = [t for t, _, _, _ in found]
        assert sorted(types) == ["dt", "ftr", "sldNum"], f"slide {n}: {found}"  # each type once
        assert all(top for _, _, top, _ in found), "a footer left inside a group"
        num = next(x for x in found if x[0] == "sldNum")
        assert num[1] == str(n) and num[3]  # renumbered, still a field
        dt = next(x for x in found if x[0] == "dt")
        assert dt[1] == "2026 年 10 月" and not dt[3]  # a fixed date stays text
    assert next(x for x in footers_on(out)[4] if x[0] == "ftr")[1] == "Grouped footer"


def test_c29_grouped_footer_without_a_position_is_not_added():
    _, out = run("sample-footer-nopos.pptx", "only", None)
    assert footers_on(out) == [[]]


# --- C30


def _long_children(n):
    return "## Big\n- parent\n" + "".join("  - x\n" for _ in range(n))


@pytest.mark.parametrize("fixture,text", [
    ("sample-bigrpr.pptx", _long_children(2100)),  # large donor a:rPr times thousands of level-2 runs
    ("sample-biglvl2.pptx", _long_children(2100)),  # small donor, large level-2 properties, thousands of children
    ("sample-heavy.pptx", "".join(f"## H{i}\n- x\n\n" for i in range(14))),  # 14 copies of 1,500 shapes
])
def test_c30_refused_before_any_output_tree(fixture, text, monkeypatch):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    built = []
    monkeypatch.setattr(sample_fill, "_copy_sample", lambda *a, **k: built.append(1))
    tracemalloc.start()
    with pytest.raises(TemplateError) as e:
        plan_deck(info, parse_outline(text), route="sample")
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert e.value.code == "too_big"
    assert not built
    assert peak < 300 * 1024 * 1024, f"planning peaked at {peak / 2**20:.0f} MB"


def test_c30_heavy_under_the_caps_fills():
    data = (FIX / "sample-heavy.pptx").read_bytes()
    info = read_template(data, "sample-heavy.pptx")
    plan = plan_deck(info, parse_outline("".join(f"## H{i}\n- x\n\n" for i in range(12))), route="sample")
    assert fill(data, "sample-heavy.pptx", plan)[:2] == b"PK"


def test_c30_paragraph_cap(monkeypatch):
    monkeypatch.setattr(sample_plan, "MAX_PARAS", 10)
    data = (FIX / "sample-design.pptx").read_bytes()
    with pytest.raises(TemplateError) as e:
        plan_deck(read_template(data, "sample-design.pptx"), parse_outline("## A\n" + "".join(f"- b{i}\n" for i in range(12))), route="sample")
    assert e.value.code == "too_big"


def test_c30_fill_rechecks_its_running_total(monkeypatch):
    data = (FIX / "sample-design.pptx").read_bytes()
    info = read_template(data, "sample-design.pptx")
    plan = plan_deck(info, parse_outline("## A\n- x\n\n## B\n- y\n"), route="sample")
    monkeypatch.setattr(sample_fill, "MAX_XML", 1000)
    with pytest.raises(TemplateError) as e:
        fill(data, "sample-design.pptx", plan)
    assert e.value.code == "too_big"


# --- C30, code review E1: the budget bounds what the fill writes, borrowed footers and escaped text included


def generated(out: bytes) -> int:
    """The generated slide XML of an output, measured as the fill's running guard measures it."""
    from sample_oracle import parts_of, slides, xml

    op = parts_of(out)
    return sum(len(etree.tostring(xml(op[n]), encoding="utf-8", xml_declaration=False)) for n in slides(op))


@pytest.mark.parametrize("fixture,text", [
    ("sample-footbig.pptx", "".join(f"## B{i}\n- x\n\n" for i in range(3))),  # each copy borrows a 1 MB footer
    ("sample-footbad.pptx", "".join(f"## B{i}\n- x\n\n" for i in range(3))),  # round 2 Edge 2: its box cannot be read
    ("sample-thin.pptx", "## Amp\n- " + "&" * 3000 + "\n- " + "<a>" * 500 + "\n- 中文" * 3 + "\n"),  # escaped text
])
def test_c30_budget_bounds_the_generated_xml(fixture, text):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    plan = plan_deck(info, parse_outline(text), route="sample")
    budget = sample_plan.plan_bytes({S.id: S for S in info.samples}, plan.slides)[0]
    assert budget >= generated(fill(data, fixture, plan))


@pytest.mark.parametrize("fixture", ["sample-footbig.pptx", "sample-footbad.pptx"])
def test_c30_borrowed_footers_refused_before_any_output_tree(fixture, monkeypatch):
    data = (FIX / fixture).read_bytes()
    info = read_template(data, fixture)
    built = []
    monkeypatch.setattr(sample_fill, "_copy_sample", lambda *a, **k: built.append(1))
    with pytest.raises(TemplateError) as e:
        plan_deck(info, parse_outline("".join(f"## B{i}\n- x\n\n" for i in range(45))), route="sample")
    assert e.value.code == "too_big" and not built
