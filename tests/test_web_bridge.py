"""The page bridge (deckfill.web): what the page receives for each step."""

import json

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


def remember(src, layout):
    """What the page keeps for an override: the slide's title, kind and which of the slides with
    that title it is, plus the layout."""
    return {"title": src["title"], "kind": src["kind"], "nth": src["nth"], "layout": layout}


def other_than_chosen(src):
    return next(lid for lid in src["compatible"] if lid != src["chosen"])


def test_override_goes_through_plan_deck(tpl):
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(outline_text("reference")))
    src = first["sources"][1]
    other = other_than_chosen(src)
    again = json.loads(s.plan(outline_text("reference"), json.dumps([remember(src, other)])))
    assert again["sources"][1]["chosen"] == other
    parts = [x["layout"] for x in again["slides"] if x["source"] == 1]
    assert parts and set(parts) == {other}  # continuation slides follow their source slide
    assert again["overrides"] == [remember(src, other)]


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
    kept = [remember(src, other)]
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
    kept = [remember(src, other)]
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
    gone = json.loads(s.plan("# 封面\n\n## 甲\n- 一\n", json.dumps([remember(src, other)])))
    assert gone["ok"] and gone["overrides"] == []
    assert gone["warnings"][0] == {"line": 0, "code": "layout_gone", "text": "乙"}
    assert [x["chosen"] for x in gone["sources"]] == [x["chosen"] for x in first["sources"][:2]]


def test_override_the_slide_no_longer_fits_is_dropped_with_a_note(tpl):
    s = Session()
    info = json.loads(s.read(tpl("typed.pptx"), "typed.pptx"))
    title_only = next(x["id"] for x in info["layouts"] if x["name"] == "Title Only")
    src = json.loads(s.plan("# 封面\n\n## 一\n- x\n"))["sources"][0]
    assert title_only in src["compatible"]
    kept = [remember(src, title_only)]
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
