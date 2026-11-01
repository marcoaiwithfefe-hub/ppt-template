"""C22 route choice (story 29): each D11 route fixture gives its stated default; sample-only fills instead of raising
no_text_layout; a template whose samples hold only titles is not offered the sample route; switching routes re-plans
and drops every pick with layout_gone (the page bridge; the page itself is the end-to-end run)."""

import json

import pytest

from conftest import FIX
from deckfill import PlanError, fill, parse_outline, plan_deck, read_template
from deckfill.web import Session

DEFAULTS = [
    ("sample-design.pptx", "sample"),
    ("layout-design.pptx", "layout"),
    ("typed.pptx", "layout"),
    ("layout-photos.pptx", "layout"),
    ("sample-typo.pptx", "sample"),
    ("sample-thin.pptx", "layout"),  # QA round 2 R4: one usable sample, so the layout route is the default
]


@pytest.mark.parametrize("fixture,route", DEFAULTS)
def test_c22_default_route(fixture, route):
    assert read_template((FIX / fixture).read_bytes(), fixture).route == route


def test_c22_sample_only_fills_instead_of_no_text_layout():
    data = (FIX / "sample-only.pptx").read_bytes()
    info = read_template(data, "sample-only.pptx")
    assert info.routes == ("sample",)
    out = fill(data, "sample-only.pptx", plan_deck(info, parse_outline("## A\n- x\n")))
    assert out[:2] == b"PK"


def test_c22_title_only_samples_get_no_sample_route():
    info = read_template((FIX / "sample-titleonly.pptx").read_bytes(), "sample-titleonly.pptx")
    assert info.routes == ("layout",)
    with pytest.raises(PlanError) as e:
        plan_deck(info, parse_outline("## A\n- x\n"), route="sample")
    assert e.value.code == "route_unavailable"


def test_c22_both_routes_offered_when_both_available():
    s = Session()
    r = json.loads(s.read((FIX / "sample-design.pptx").read_bytes(), "sample-design.pptx"))
    assert r["routes"] == ["sample", "layout"] and r["route"] == "sample"
    assert [x["id"] for x in r["samples"]] == ["s1", "s2", "s3", "s4", "s5", "s6"]


def test_c22_switching_replans_and_drops_every_pick():
    s = Session()
    s.read((FIX / "sample-design.pptx").read_bytes(), "sample-design.pptx")
    text = "## A\n- x\n\n## B\n- y\n"
    first = json.loads(s.plan(text, "[]", "sample"))
    pick = {"title": "A", "kind": "content", "nth": 0, "count": 1, "layout": "s6", "route": "sample"}
    picked = json.loads(s.plan(text, json.dumps([pick]), "sample"))
    assert picked["sources"][0]["chosen"] == "s6" and picked["overrides"] == [pick]
    switched = json.loads(s.plan(text, json.dumps(picked["overrides"]), "layout"))
    assert switched["route"] == "layout" and switched["overrides"] == []
    assert [w["code"] for w in switched["warnings"]].count("layout_gone") == 1
    assert switched["sources"][0]["chosen"].startswith("/ppt/slideLayouts/")
    assert first["route"] == "sample"
