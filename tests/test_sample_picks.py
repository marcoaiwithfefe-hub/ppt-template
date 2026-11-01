"""D12 overrides: the rev 6 and rev 7 pick-tracking rules on s<k> ids, through the page bridge: a pick follows its
slide after an insert above it, a deleted slide's pick goes with layout_gone, repeated titles keep their own picks
while their group keeps its size, and a pick in a repeated-title group whose size changes is dropped, never moved."""

import json

from conftest import FIX
from deckfill.web import Session


def session():
    s = Session()
    s.read((FIX / "sample-design.pptx").read_bytes(), "sample-design.pptx")
    return s


def pick(title, nth, count, sample):
    return {"title": title, "kind": "content", "nth": nth, "count": count, "layout": sample, "route": "sample"}


def chosen(reply):
    return [(src["title"], src["chosen"]) for src in reply["sources"]]


def codes(reply):
    return [w["code"] for w in reply["warnings"]]


def test_pick_follows_its_slide_after_an_insert():
    s = session()
    before = json.loads(s.plan("## A\n- x\n\n## B\n- y\n", json.dumps([pick("B", 0, 1, "s5")]), "sample"))
    assert dict(chosen(before))["B"] == "s5"
    after = json.loads(s.plan("## New\n- n\n\n## A\n- x\n\n## B\n- y\n", json.dumps(before["overrides"]), "sample"))
    assert dict(chosen(after))["B"] == "s5" and after["overrides"] == before["overrides"]


def test_deleted_slide_pick_is_gone():
    s = session()
    r = json.loads(s.plan("## A\n- x\n", json.dumps([pick("B", 0, 1, "s5")]), "sample"))
    assert codes(r).count("layout_gone") == 1 and r["overrides"] == []


def test_repeated_titles_keep_their_own_picks():
    s = session()
    text = "## Same\n- a\n\n## Same\n- b\n"
    r = json.loads(s.plan(text, json.dumps([pick("Same", 1, 2, "s5")]), "sample"))
    assert [c for t, c in chosen(r)][1] == "s5"
    again = json.loads(s.plan("## Top\n- t\n\n" + text, json.dumps(r["overrides"]), "sample"))
    assert [c for t, c in chosen(again)][2] == "s5"


def test_repeated_title_group_size_change_drops_the_pick():
    s = session()
    r = json.loads(s.plan("## Same\n- a\n\n## Same\n- b\n", json.dumps([pick("Same", 1, 2, "s5")]), "sample"))
    shrunk = json.loads(s.plan("## Same\n- a\n", json.dumps(r["overrides"]), "sample"))
    assert codes(shrunk).count("layout_gone") == 1 and shrunk["overrides"] == []
    grown = json.loads(s.plan("## Same\n- a\n\n## Same\n- b\n\n## Same\n- c\n", json.dumps(r["overrides"]), "sample"))
    assert codes(grown).count("layout_gone") == 1 and grown["overrides"] == []


def test_incompatible_sample_pick_falls_back_with_layout_dropped():
    s = session()
    two = {**pick("Two", 0, 1, "s1"), "kind": "two"}
    r = json.loads(s.plan("## Two\n- a\n||\n- b\n", json.dumps([two]), "sample"))
    # s1 has no body box, so a two-column slide cannot use it: the slide takes its default, s6 (QA round 2 R6: the pool
    # runs across the two class and its content fallback; s6 merges both columns and leaves no box unused, s4 leaves two)
    assert "layout_dropped" in codes(r) and chosen(r) == [("Two", "s6")] and r["overrides"] == []
