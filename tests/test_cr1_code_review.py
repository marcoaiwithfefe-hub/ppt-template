"""Code review round 1 fixes (rev 8, fix-cr1). Expected outcomes are written from the review's findings and the spec,
never read from the planner.

F2: reading a sample's custom geometry never raises; a guide-name path is not a backing; any other error while reading
one sample slide makes only that sample unusable (reason "unreadable", the error kept in the template info); the layout
route keeps filling on a template whose sample slides are malformed.
"""

import pytest

from conftest import FIX
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill import sample as sample_mod
from deckfill.package import check_integrity, load

OUTLINE = "# Deck\n\n## One\n- first point\n- second point\n\n## Two\n- third point\n"


def malformed():
    data = (FIX / "sample-malformed.pptx").read_bytes()
    return data, read_template(data, "sample-malformed.pptx")


# ---------------------------------------------------------------------------------------------------------------- F2


def test_f2_template_with_guide_paths_and_a_malformed_sample_reads():
    _, info = malformed()
    by = {S.id: S for S in info.samples}
    assert [S.id for S in info.samples] == ["s1", "s2", "s3"]
    assert by["s1"].usable and by["s2"].usable
    assert not by["s3"].usable and by["s3"].reason == "unreadable"
    assert "ValueError" in by["s3"].error
    assert info.routes == ("sample", "layout")


def test_f2_guide_name_corners_are_not_a_backing():
    _, info = malformed()
    chip = next(lf for lf in info.samples[1].leaves if lf.sid == 211)
    assert chip.rect is False


def test_f2_layout_route_fills_on_malformed_samples():
    data, info = malformed()
    out = fill(data, "sample-malformed.pptx", plan_deck(info, parse_outline(OUTLINE), route="layout"))
    assert check_integrity(load(out, "out.pptx").parts) == []


def test_f2_sample_route_never_uses_the_unreadable_sample():
    data, info = malformed()
    plan = plan_deck(info, parse_outline(OUTLINE), route="sample")
    assert "s3" not in {ps.layout for ps in plan.slides}
    assert "s3" not in {c for cs in plan.compatible for c in cs}
    out = fill(data, "sample-malformed.pptx", plan)
    assert check_integrity(load(out, "out.pptx").parts) == []


def test_f2_footer_reading_failure_makes_only_that_sample_unusable(monkeypatch):
    real = sample_mod.footer_boxes
    calls = {"n": 0}

    def flaky(tree, layout_el=None, master_el=None):
        if layout_el is not None and master_el is not None:  # the per-slide pass
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("invalid literal for int() with base 10: 'bad'")
        return real(tree, layout_el, master_el)

    monkeypatch.setattr(sample_mod, "footer_boxes", flaky)
    data = (FIX / "sample-design.pptx").read_bytes()
    info = read_template(data + b"", "sample-design-footer-fault.pptx")
    assert [S.usable for S in info.samples][:3] == [True, False, True]
    assert info.samples[1].reason == "unreadable" and "ValueError" in info.samples[1].error


@pytest.mark.parametrize("value,expected", [("0", 0), ("-12", -12), ("+7", 7), ("w", None), ("h", None),
                                            ("gd1", None), ("1.5", None), ("", None), (None, None)])
def test_f2_coord(value, expected):
    assert sample_mod._coord(value) == expected


# ---------------------------------------------------------------------------------------------------------------- F1

MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def altcontent():
    data = (FIX / "sample-altcontent.pptx").read_bytes()
    return data, read_template(data, "sample-altcontent.pptx")


def test_f1_reader_and_chart_exclusion_read_the_fallback_tree():
    _, info = altcontent()
    s1, s2, s3 = info.samples
    assert s1.usable and [b.text for b in s1.boxes] == ["Alt one", "Fallback body words", "Fallback note"]
    assert s2.usable and {lf.tag for lf in s2.leaves if lf.sid == 231} == {"pic"}  # the choice's table is not read
    assert not s3.usable and s3.reason == "chart, table or diagram"  # the fallback's table is


def test_f1_copies_hold_no_alternate_content_and_no_choice_table():
    from sample_oracle import parts_of, slides

    data, info = altcontent()
    out = fill(data, "sample-altcontent.pptx", plan_deck(info, parse_outline("## A\n- one\n\n## B\n- two\n"), route="sample"))
    parts = parts_of(out)
    from lxml import etree

    for name in slides(parts):
        root = etree.fromstring(parts[name])
        assert root.find(".//" + MC + "AlternateContent") is None and root.find(".//" + MC + "Choice") is None
        assert root.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}tbl") is None
        assert b"Choice" not in parts[name]
    assert check_integrity(load(out, "out.pptx").parts) == []


def test_f1_normalise_nested_and_missing_fallback():
    from lxml import etree

    from deckfill.sample import normalise_alternates

    root = etree.fromstring(
        '<r xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
        '<mc:AlternateContent><mc:Choice Requires="x"><c1/></mc:Choice><mc:Fallback><f1/>'
        '<mc:AlternateContent><mc:Choice Requires="x"><c2/></mc:Choice><mc:Fallback><f2/></mc:Fallback>'
        '</mc:AlternateContent></mc:Fallback></mc:AlternateContent>'
        '<k/><mc:AlternateContent><mc:Choice Requires="x"><c3/></mc:Choice></mc:AlternateContent></r>')
    assert normalise_alternates(root) == 3
    assert [c.tag for c in root] == ["f1", "f2", "k"]
