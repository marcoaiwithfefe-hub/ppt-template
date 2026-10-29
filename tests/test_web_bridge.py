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
    deck = read_deck(s.fill())
    assert len(deck) == len(plan["slides"])


def test_override_goes_through_plan_deck(tpl):
    s = Session()
    s.read(tpl("typed.pptx"), "typed.pptx")
    first = json.loads(s.plan(outline_text("reference")))
    src = first["sources"][1]
    other = next(lid for lid in src["compatible"] if lid != src["chosen"])
    again = json.loads(s.plan(outline_text("reference"), json.dumps({"1": other})))
    assert again["sources"][1]["chosen"] == other
    parts = [x["layout"] for x in again["slides"] if x["source"] == 1]
    assert parts and set(parts) == {other}  # continuation slides follow their source slide


def test_errors_come_back_as_codes(tpl):
    s = Session()
    assert json.loads(s.read(tpl("no-body.pptx"), "n.pptx")) == {"ok": False, "code": "no_text_layout"}
    s.read(tpl("typed.pptx"), "typed.pptx")
    assert json.loads(s.plan("plain text, no slides"))["code"] == "no_slides"


def test_file_name_is_windows_safe():
    assert file_name('季度/報告: "草稿"?') == "季度 報告 草稿"
    assert file_name("   ") == "簡報"
