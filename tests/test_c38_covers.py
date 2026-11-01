"""C38 covers and columns first (QA round 3 S1): inside the readable pool the slide's own class comes first; a fallback
class is used only when no readable candidate of the slide's own class exists. Expected picks are written from the
spec's QA round 3 section."""

from conftest import FIX
from deckfill import parse_outline, plan_deck, read_template
from deckfill.sample_plan import SMALL_TEXT, build, rank_key, readable

COVER = "# Annual operations plan 2027\nOperations team briefing\n\n## A\n- x\n"


def plan(fixture, text, overrides=None):
    info = read_template((FIX / fixture).read_bytes(), fixture)
    return info, plan_deck(info, parse_outline(text), overrides, route="sample")


def test_c38_fully_readable_cover_takes_the_title_slide():
    """The cover needs a shrink and the content sample fits at full size, so the ranking alone would pick the content
    sample; the cover is fully readable (title and subtitle), so the title class comes first."""
    info, p = plan("sample-cover.pptx", COVER)
    s = parse_outline(COVER).slides[0]
    c1, c2 = info.samples[0], info.samples[1]
    assert readable(c1, build(c1, s)) and readable(c2, build(c2, s))
    assert rank_key(c2, s, build(c2, s)) < rank_key(c1, s, build(c1, s))
    assert p.chosen[0] == "s1"


def test_c38_cover_whose_subtitle_misses_q3_loses_to_a_readable_fallback():
    info, p = plan("sample-cover2.pptx", COVER)
    s = parse_outline(COVER).slides[0]
    c1 = info.samples[0]
    assert [b.role for b in build(c1, s).parts[0].boxes] == ["title", "subtitle"] and not readable(c1, build(c1, s))
    assert p.chosen[0] == "s2" and SMALL_TEXT not in p.slides[0].flags


def test_c38_two_column_slide_uses_a_readable_two_sample_before_any_merge():
    _, p = plan("sample-design.pptx", "## Compare\n- Old way\n||\n- New way\n")
    assert p.chosen == ("s4",)
    assert "columns_merged" not in [w.code for w in p.warnings]
    assert [b.sid for b in p.slides[0].boxes] == [401, 411, 412]


def test_c38_unreadable_cover_still_moves_the_title_slide_to_a_readable_content_sample():
    _, p = plan("sample-readable.pptx", "# Big cover\n\n## A\n- x\n")
    assert p.chosen[0] in ("s2", "s3") and SMALL_TEXT not in p.slides[0].flags


def test_c38_user_picks_are_kept():
    _, p = plan("sample-cover.pptx", COVER, {0: "s2"})
    assert p.chosen[0] == "s2"
    _, q = plan("sample-readable.pptx", "# Big cover\n\n## A\n- x\n", {0: "s1"})
    assert q.chosen[0] == "s1" and SMALL_TEXT in q.slides[0].flags  # kept below the bar, warned
