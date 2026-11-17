"""C2, silent break: layout picks and column order."""

import dataclasses

import pytest
from conftest import outline_text
from oracle import deck_lines, read_deck

from deckfill import PlanError, TemplateError, Warning, fill, parse_outline, plan_deck, read_template

L = "/ppt/slideLayouts/slideLayout%d.xml"


def classes(info):
    return {lay.name: lay.cls for lay in info.layouts}


def test_typed_classes_and_defaults(tpl):
    info = read_template(tpl("typed.pptx"), "typed.pptx")
    c = classes(info)
    assert c["Title Slide"] == "title"
    assert c["Title and Content"] == "content"
    assert c["Two Content"] == "two"
    assert c["Comparison"] == "two"
    assert c["Section Header"] == "section"
    assert c["Title Only"] == "section"
    assert c["Blank"] == "other"
    assert dict(info.defaults) == {"title": L % 1, "content": L % 2, "two": L % 4, "section": L % 3}


def test_custom_classes_by_placeholders_not_names(tpl):
    info = read_template(tpl("custom.pptx"), "custom.pptx")
    c = classes(info)
    assert c["標題投影片"] == "title"
    assert c["標題及內容"] == "content"
    assert c["兩欄內容"] == "two"
    assert c["章節標題"] == "content"  # untyped: title plus one body is content (D3 step 2)
    assert c["只有標題"] == "section"
    assert c["比較"] == "other"  # four bodies
    assert dict(info.defaults) == {"title": L % 1, "content": L % 2, "two": L % 4, "section": L % 6}


def test_custom_left_column_lands_in_left_placeholder(tpl):
    data = tpl("custom.pptx")
    info = read_template(data, "c.pptx")
    two = info.layout(L % 4)
    # the right column's placeholder comes first in XML
    assert [b.idx for b in two.bodies] == [2, 1]
    assert two.columns == (1, 2)
    plan = plan_deck(info, parse_outline("## t\n- 左\n||\n- 右"))
    deck = read_deck(fill(data, "c.pptx", plan))
    assert deck[0].bodies == [[(1, "左")], [(1, "右")]]


def test_two_masters_defaults_come_from_first_master(tpl):
    info = read_template(tpl("two-masters.pptx"), "m.pptx")
    assert len(info.masters) == 2 and len(info.layouts) == 22
    for cls, lid in info.defaults:
        assert info.layout(lid).master == 0
    assert {lay.cls for lay in info.layouts if lay.master == 1} >= {"title", "content", "two", "section"}


def test_no_two_has_no_two_default(tpl):
    info = read_template(tpl("no-two.pptx"), "n.pptx")
    assert info.default("two") is None


def test_twoobj_with_one_body_is_not_two(tpl):
    info = read_template(tpl("contradict.pptx"), "c.pptx")
    lay = next(x for x in info.layouts if x.name == "Two Content")
    assert lay.cls == "content"
    assert info.default("two") == L % 5  # Comparison


def test_no_body_raises(tpl):
    with pytest.raises(TemplateError) as e:
        read_template(tpl("no-body.pptx"), "n.pptx")
    assert e.value.code == "no_text_layout"


def test_override_is_used_in_plan_and_output(tpl):
    data = tpl("two-masters.pptx")
    info = read_template(data, "m.pptx")
    b_content = next(x.id for x in info.layouts if x.name == "B Title and Content")
    outline = parse_outline(outline_text("reference"))
    plan = plan_deck(info, outline, {1: b_content})
    assert plan.chosen[1] == b_content
    assert [s.layout for s in plan.slides if s.source == 1] == [b_content]
    deck = read_deck(fill(data, "m.pptx", plan))
    assert deck[1].layout_name == "B Title and Content"
    assert deck[1].title == "三個目標"


def test_compatible_lists_exclude_layouts_without_destination(tpl):
    info = read_template(tpl("typed.pptx"), "t.pptx")
    outline = parse_outline(outline_text("reference"))
    plan = plan_deck(info, outline)
    names = {lay.id: lay.name for lay in info.layouts}
    bullets = [names[i] for i in plan.compatible[1]]
    assert "Title Only" not in bullets and "Blank" not in bullets and "Title Slide" not in bullets
    assert "Title and Content" in bullets
    section = [names[i] for i in plan.compatible[5]]
    assert "Title Only" in section and "Blank" not in section


def test_incompatible_override_falls_back_to_the_default_with_a_warning(tpl):
    """Layout-override fix: a bullet slide overridden onto Title Only gets its default layout and
    a layout_dropped warning, and the deck fills, instead of the plan failing."""
    data = tpl("typed.pptx")
    info = read_template(data, "t.pptx")
    outline = parse_outline(outline_text("reference"))
    title_only = next(x.id for x in info.layouts if x.name == "Title Only")
    plan = plan_deck(info, outline, {1: title_only})
    assert plan.chosen[1] == L % 2
    assert Warning(4, "layout_dropped", "三個目標") in plan.warnings
    assert read_deck(fill(data, "t.pptx", plan))[1].layout_name == "Title and Content"


def test_out_of_range_override_is_dropped_with_a_warning(tpl):
    data = tpl("typed.pptx")
    info = read_template(data, "t.pptx")
    outline = parse_outline(outline_text("reference"))
    plan = plan_deck(info, outline, {99: L % 2})
    assert plan.chosen == plan_deck(info, outline).chosen
    assert Warning(0, "layout_gone", "") in plan.warnings
    assert len(read_deck(fill(data, "t.pptx", plan))) == len(plan.slides)


def test_bullet_slide_on_title_only_is_refused_by_fill(tpl):
    data = tpl("typed.pptx")
    info = read_template(data, "t.pptx")
    outline = parse_outline(outline_text("reference"))
    title_only = next(x.id for x in info.layouts if x.name == "Title Only")
    # a plan hand-built with that layout is refused by fill
    good = plan_deck(info, outline)
    bad_slide = dataclasses.replace(good.slides[1], layout=title_only)
    bad = dataclasses.replace(good, slides=good.slides[:1] + (bad_slide,) + good.slides[2:])
    with pytest.raises(PlanError) as e:
        fill(data, "t.pptx", bad)
    assert e.value.code == "stale_plan"


@pytest.mark.parametrize(
    "edit",
    [
        lambda p: dataclasses.replace(p, slides=p.slides[:-1]),  # a slide dropped
        lambda p: dataclasses.replace(p, slides=tuple(dataclasses.replace(s, fit="fits") for s in p.slides)),
        lambda p: dataclasses.replace(p, overrides=((1, L % 4),)),  # overrides without recompute
    ],
)
def test_fill_refuses_hand_edited_plan(edit, tpl):
    data = tpl("typed.pptx")
    info = read_template(data, "t.pptx")
    plan = plan_deck(info, parse_outline(outline_text("reference")))
    with pytest.raises(PlanError) as e:
        fill(data, "t.pptx", edit(plan))
    assert e.value.code == "stale_plan"


@pytest.mark.parametrize(
    "template,expect",
    [
        ("no-two.pptx", {3: "content"}),
        ("no-section.pptx", {5: "title"}),
        ("no-title.pptx", {0: "content"}),
        ("only-content.pptx", {0: "content", 3: "content", 5: "content"}),
    ],
)
def test_fallback_layout_classes(template, expect, tpl):
    data = tpl(template)
    info = read_template(data, template)
    plan = plan_deck(info, parse_outline(outline_text("reference")))
    for i, cls in expect.items():
        assert info.layout(plan.chosen[i]).cls == cls
    # the C1 assertion for these runs lives in test_c1_text (golden per fallback)
    assert deck_lines(read_deck(fill(data, template, plan)))
