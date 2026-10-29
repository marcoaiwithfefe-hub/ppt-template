"""The page bridge (deckfill.web): what the page receives for each step."""

import json

import pytest

from conftest import outline_text
from oracle import read_deck

from deckfill.web import Session, file_name


def test_read_plan_fill_round(tpl):
    s = Session()
    info = json.loads(s.read(tpl("typed.pptx"), "typed.pptx"))
    assert info["ok"] and info["masters"] == 1
    assert set(info["defaults"]) == {"title", "content", "two", "section"}
    plan = json.loads(s.plan(outline_text("reference")))
    assert plan["ok"] and plan["name"] == "匯通物流 2027 年度計劃"
    assert [x["fit"] for x in plan["slides"]].count("split") == 2
    deck = read_deck(s.fill(outline_text("reference")))
    assert len(deck) == len(plan["slides"])
    assert s.fill_name == plan["name"]


def test_fill_plans_from_the_text_it_is_given(tpl):
    """Codex round 1 F1: the last plan() call was for older text; fill must use the text it gets."""
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    s.plan("# OLD\n\n## 一\n- 舊")
    deck = read_deck(s.fill("# NEW\n\n## 一\n- 新"))
    assert deck[0].title == "NEW" and s.fill_name == "NEW"
    assert [t for _, t in deck[1].bodies[0]] == ["新"]


def remember(plan, i, layout):
    """What the page keeps for an override of slide i: its title and kind, which of the slides
    with that title and kind it is (nth), how many there are (count, F16), and the layout."""
    src = plan["sources"][i]
    count = sum((x["title"], x["kind"]) == (src["title"], src["kind"]) for x in plan["sources"])
    return {"title": src["title"], "kind": src["kind"], "nth": src["nth"], "count": count, "layout": layout}


def other_than_chosen(src):
    return next(lid for lid in src["compatible"] if lid != src["chosen"])


def test_override_goes_through_plan_deck(tpl):
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(outline_text("reference")))
    src = first["sources"][1]
    other = other_than_chosen(src)
    again = json.loads(s.plan(outline_text("reference"), json.dumps([remember(first, 1, other)])))
    assert again["sources"][1]["chosen"] == other
    parts = [x["layout"] for x in again["slides"] if x["source"] == 1]
    assert parts and set(parts) == {other}  # continuation slides follow their source slide
    assert again["overrides"] == [remember(first, 1, other)]


THREE = "# 封面\n\n## 甲\n- 一\n\n## 乙\n- 二\n"
INSERTED = "# 封面\n\n## 新\n- 新\n\n## 甲\n- 一\n\n## 乙\n- 二\n"


def test_override_follows_its_slide_after_an_insert(tpl):
    """Layout-override fix: a slide inserted above an overridden one must not move the layout
    onto the slide that now sits at the old position."""
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(THREE))
    src = first["sources"][2]
    other = other_than_chosen(src)
    kept = [remember(first, 2, other)]
    again = json.loads(s.plan(INSERTED, json.dumps(kept)))
    by_title = {x["title"]: x["chosen"] for x in again["sources"]}
    assert by_title["乙"] == other
    assert by_title["甲"] == src["chosen"]  # the slide now at index 2 keeps its default
    assert again["overrides"] == kept
    deck = read_deck(s.fill(INSERTED, json.dumps(kept)))
    names = {x["id"]: x["name"] for x in json.loads(s.read(tpl("typed.pptx"), "typed.pptx"))["layouts"]}
    assert [d.layout_name for d in deck if d.title == "乙"] == [names[other]]


def test_override_on_a_repeated_title_stays_on_its_slide(tpl):
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    text = "# 封面\n\n## 重複\n- a\n\n## 重複\n- b\n"
    first = json.loads(s.plan(text))
    src = first["sources"][2]
    assert src["nth"] == 1
    other = other_than_chosen(src)
    kept = [remember(first, 2, other)]
    same = json.loads(s.plan(text, json.dumps(kept)))
    assert [x["chosen"] for x in same["sources"]][1:] == [first["sources"][1]["chosen"], other]
    moved = json.loads(s.plan("# 封面\n\n## 新\n- 新\n\n" + text.split("\n\n", 1)[1], json.dumps(kept)))
    assert [x["chosen"] for x in moved["sources"]][2:] == [first["sources"][1]["chosen"], other]


def test_override_for_a_deleted_slide_is_dropped_with_a_note(tpl):
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(THREE))
    src = first["sources"][2]
    other = other_than_chosen(src)
    gone = json.loads(s.plan("# 封面\n\n## 甲\n- 一\n", json.dumps([remember(first, 2, other)])))
    assert gone["ok"] and gone["overrides"] == []
    assert gone["warnings"][0] == {"line": 0, "code": "layout_gone", "text": "乙"}
    assert [x["chosen"] for x in gone["sources"]] == [x["chosen"] for x in first["sources"][:2]]


def test_override_the_slide_no_longer_fits_is_dropped_with_a_note(tpl):
    s = Session()
    info = json.loads(s.read(tpl("typed.pptx"), "typed.pptx"))
    title_only = next(x["id"] for x in info["layouts"] if x["name"] == "Title Only")
    first = json.loads(s.plan("# 封面\n\n## 一\n- x\n"))
    src = first["sources"][0]
    assert title_only in src["compatible"]
    kept = [remember(first, 0, title_only)]
    assert json.loads(s.plan("# 封面\n\n## 一\n- x\n", json.dumps(kept)))["overrides"] == kept
    # a subtitle line makes the cover need a subtitle box, which Title Only does not have
    after = json.loads(s.plan("# 封面\n副題\n\n## 一\n- x\n", json.dumps(kept)))
    assert after["ok"] and after["overrides"] == []
    assert after["sources"][0]["chosen"] != title_only
    assert {"line": 1, "code": "layout_dropped", "text": "封面"} in after["warnings"]


def test_errors_come_back_as_codes(tpl):
    s = Session()
    assert json.loads(s.read(tpl("no-body.pptx"), "n.pptx")) == {"ok": False, "code": "no_text_layout"}
    s.read(tpl("typed.pptx"), "typed.pptx")
    assert json.loads(s.plan("plain text, no slides"))["code"] == "no_slides"


def test_file_name_is_windows_safe():
    assert file_name('季度/報告: "草稿"?') == "季度 報告 草稿"
    assert file_name("   ") == "簡報"


PAIR = "# 封面\n\n## Status\n- a\n\n## Status\n- b\n"


def pair_session(tpl, pick):
    """Two content slides titled Status; a layout picked for the one at index pick (1 or 2)."""
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(PAIR))
    other = other_than_chosen(first["sources"][pick])
    return s, first, [remember(first, pick, other)], other


def assert_dropped(reply, default, other):
    assert reply["ok"] and reply["overrides"] == []
    assert {"line": 0, "code": "layout_gone", "text": "Status"} in reply["warnings"]
    assert all(x["chosen"] == default for x in reply["sources"] if x["title"] == "Status")
    assert all(x["chosen"] != other for x in reply["sources"])  # never moved to a sibling


@pytest.mark.parametrize(
    "pick, edited",
    [
        (1, "# 封面\n\n## Status\n- b\n"),  # pick the first, delete the first
        (2, "# 封面\n\n## Status\n- b\n"),  # pick the second, delete the first
        (1, "# 封面\n\n## Status 新\n- a\n\n## Status\n- b\n"),  # rename the picked one
        (1, "# 封面\n\n## Status\n- z\n\n" + PAIR.split("\n\n", 1)[1]),  # a third Status inserted
    ],
    ids=["pick-first-delete-first", "pick-second-delete-first", "rename-picked", "insert-third"],
)
def test_f16_a_pick_is_dropped_when_its_same_titled_group_changes(pick, edited, tpl):
    """Codex round 3, F16: title, kind and nth cannot tell same-titled slides apart once the group
    changes, so the pick is dropped with layout_gone and never moves to a sibling."""
    s, first, kept, other = pair_session(tpl, pick)
    default = first["sources"][1]["chosen"]
    assert_dropped(json.loads(s.plan(edited, json.dumps(kept))), default, other)
    deck = read_deck(s.fill(edited, json.dumps(kept)))
    names = {x["id"]: x["name"] for x in json.loads(s.read(tpl("typed.pptx"), "typed.pptx"))["layouts"]}
    assert all(d.layout_name == names[default] for d in deck if d.title.startswith("Status"))
