"""C46 (rev 9 QA round 1, Q9-1 to Q9-4) on sample-round1 (1440 by 810 pt) and on the real templates.

Expected values are computed by hand from the spec and the fixture (fixtures/make_rev9_fixtures.py make_round1):
- r2: the title box is 450 pt wide inside its insets. 預算 港幣 800 萬 is 8.3 em by plan.text_lines (six glyphs at
  1 em, two spaces and "800 " at 0.55 em a character), so 萬 sits alone on line 2 at 60 pt (498 pt) and 57 pt (473.1
  pt) and the title sets one line at 54 pt (448.2 pt): written 5400.
- r3: the box is 2.05 em wide inside its insets at every step from 100% to 70%, so three glyphs always set 2 + 1, and
  two lines fit its height only at the 42 pt floor: written 4200 with the orphan.
The real-template checks run only where qa/real-templates holds the decks (gitignored; a missing deck is NOT RUN)."""

from pathlib import Path

import pytest

from conftest import FIX, ROOT
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.outline import Item
from sample_look import look_diff
from sample_oracle import parts_of, slides, tree_of, xml

NAME = "sample-round1.pptx"
REAL = ROOT / "qa" / "real-templates"


def run(path: Path, text: str, ovr=None, route="sample"):
    data = path.read_bytes()
    info = read_template(data, path.name)
    plan = plan_deck(info, parse_outline(text), ovr, route=route)
    return data, info, plan, fill(data, path.name, plan)


def ids_on(out: bytes, n: int) -> set[int]:
    parts = parts_of(out)
    tree = tree_of(parts[slides(parts)[n]])
    return {int(c.get("id")) for c in tree.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")}


def real(name: str) -> Path:
    path = REAL / name
    if not path.exists():
        pytest.skip(f"{name} is not in qa/real-templates (NOT RUN)")
    return path


# Q9-1 -----------------------------------------------------------------------------------------


def test_c46_q91_unclampable_box_leaves_the_subtitle_role():
    data, _, plan, out = run(FIX / NAME, "# 匯通物流 2027 年度計劃\n營運部 · 內部簡報\n")
    cover = plan.slides[0]
    assert cover.layout == "s1"
    sub = next(bf for bf in cover.boxes if bf.role == "subtitle")
    assert sub.sid == 111, "the subtitle goes to the next body box, never the box T4 cannot clamp"
    assert "check" not in cover.flags and sub.status != "check"
    assert look_diff(out, data) == []


def test_c46_q91_only_body_keeps_check():
    data, _, plan, out = run(FIX / NAME, "# Deck\n\n## Only body\n- Body text\n", {1: "s5"})
    bf = next(b for b in plan.slides[1].boxes if b.role == "body")
    assert bf.sid == 511 and bf.status == "check" and bf.box is None, "no other candidate remains: the sample box"
    assert "check" in plan.slides[1].flags
    assert look_diff(out, data) == []


def test_c46_q91_elegant_cover_has_no_check():
    _, _, plan, _ = run(real("elegant-pitch-deck.pptx"), (ROOT / "fixtures" / "reference-outline.md").read_text())
    cover = plan.slides[0]
    assert "check" not in cover.flags
    assert next(bf for bf in cover.boxes if bf.role == "subtitle").sid != 138, "box 138 crosses the top-left edges"


# Q9-2 -----------------------------------------------------------------------------------------


def test_c46_q92_business_conference_budget_merges_on_s3(monkeypatch):
    """Q9-2's S2 rule: with business-conference's two-column tier as it stood at 135093a (pair columns tried only when
    built columns fail, so s7 and s10 offered none), the warned s2 columns yield to round 3's merged s3."""
    import deckfill.sample_plan as sp

    path = real("business-conference-slides.pptx")
    monkeypatch.setattr(sp, "pair_columns", lambda S, columns: None)
    _, _, plan, _ = run(path, (ROOT / "fixtures" / "reference-outline.md").read_text())
    k = next(i for i, s in enumerate(plan.outline.slides) if s.title == "預算 港幣 800 萬")
    assert plan.chosen[k] == "s3", "round 3's merged s3"
    budget = [ps for ps in plan.slides if ps.source == k]
    assert len(budget) == 1
    assert ("columns_merged", "預算 港幣 800 萬") in [(w.code, w.text) for w in plan.warnings]
    assert all(bf.status != "warned" for bf in budget[0].boxes)


def test_c46_q92_business_conference_budget_unwarned_at_head():
    """At the fix head (Codex F1: pair columns also when no built columns exist) s7 and s10 offer unwarned pair
    columns, which T5 ranks in the two-column tier above the merge: 預算 is one slide with no fit warning (flagged to
    Fable: C46 names s3)."""
    _, _, plan, _ = run(real("business-conference-slides.pptx"), (ROOT / "fixtures" / "reference-outline.md").read_text())
    k = next(i for i, s in enumerate(plan.outline.slides) if s.title == "預算 港幣 800 萬")
    budget = [ps for ps in plan.slides if ps.source == k]
    assert len(budget) == 1 and "warned" not in budget[0].flags
    assert all(bf.status != "warned" for bf in budget[0].boxes)


# Q9-3 -----------------------------------------------------------------------------------------


def test_c46_q93_orphan_glyph_steps_the_title_down():
    data, _, plan, out = run(FIX / NAME, "# Deck\n\n## 預算 港幣 800 萬\n- Body\n", {1: "s2"})
    t = next(bf for bf in plan.slides[1].boxes if bf.role == "title")
    assert t.sizes[0] == 5400, "two 5% steps: 萬 joins line 1 at 54 pt"
    assert t.box is None, "the title fits at full size, so T6 does not grow it"
    assert look_diff(out, data) == []


def test_c46_q93_title_at_its_floor_keeps_the_orphan():
    _, _, plan, _ = run(FIX / NAME, "# Deck\n\n## 預算書\n- Body\n", {1: "s3"})
    t = next(bf for bf in plan.slides[1].boxes if bf.role == "title")
    assert t.sizes[0] == 4200, "at the 70% floor the largest fitting size stands"
    assert t.status == "shrunk" and t.box is None


# Q9-4 -----------------------------------------------------------------------------------------


def test_c46_q94_cleared_caption_frame_goes_and_a_large_one_stays():
    data, _, plan, out = run(FIX / NAME, "# Deck\n\n## 團隊更新\n", {1: "s4"})
    ids = ids_on(out, 1)
    assert not {415, 425} & ids, "both captions are cleared"
    assert 411 not in ids, "the 2.6% line-only frame behind a cleared caption is its backing: it goes"
    assert 421 in ids, "the 9.1% frame stays (Q1's size rule)"
    assert look_diff(out, data) == []


def test_c46_q94_canva_s6_has_no_empty_frame():
    data, _, plan, out = run(real("canva-red-pink-pitch.pptx"), "# 匯通物流 2027 年度計劃\n\n## 問答\n", {1: "s6"})
    ids = ids_on(out, 1)
    assert not {9, 13, 17} & ids, "the captions are cleared"
    assert not {6, 11, 15} & ids, "their line-only frames go with them"
    # C23 on the 問答 slide only: on this deck the comparator's signature match pairs the cover copy (s1) with s7,
    # whose shape ids it shares (a matching limit outside Q9-4, reported as a follow-up)
    assert [d for d in look_diff(out, data) if d.startswith("slide 2 ")] == []


# Codex rev 9 round 1 ------------------------------------------------------------------------------


def test_e1_display_title_clamps_at_its_own_floor():
    info = read_template((FIX / NAME).read_bytes(), NAME)
    S = next(x for x in info.samples if x.id == "s6")
    t = S.box(601)
    assert t.unmodelled == "" and 601 not in S.edge, "the clamped box holds a 60 pt line at the display floor"
    assert t.x == 100 * 12700 and t.orig is not None


def test_f2_display_title_steps_rank_past_seven():
    from deckfill.sample_plan import build, rank_key

    info = read_template((FIX / NAME).read_bytes(), NAME)
    s = parse_outline("## ABCDEFGHIJ\n- Body text\n").slides[0]
    by = {x.id: x for x in info.samples}
    b7, b8 = build(by["s7"], s), build(by["s8"], s)
    t7, t8 = b7.parts[0].boxes[0], b8.parts[0].boxes[0]
    assert (t7.sizes[0], t7.box) == (6000, None) and (t8.sizes[0], t8.box) == (7800, None), "steps 10 and 7, ungrown"
    assert rank_key(by["s8"], s, b8) < rank_key(by["s7"], s, b7), "78 pt beats 60 pt; file order never decides"


def test_f3_pair_builds_count_only_boxes_with_text():
    from deckfill.sample_plan import build

    info = read_template((FIX / "sample-pairs.pptx").read_bytes(), "sample-pairs.pptx")
    S = next(x for x in info.samples if x.id == "s1")
    # three points: slot group (111, 112) has two slots, (121, 122, 123) fails Q3, so the pair group takes them
    content = build(S, parse_outline("## Three\n- a\n- b\n- c\n").slides[0])
    assert content.pairs and content.unused == len(S.bodies) - 3, "three childless bullets fill H1 to H3 only"
    kids = build(S, parse_outline("## Three\n- a\n  - a child\n- b\n- c\n").slides[0])
    assert kids.pairs and kids.unused == len(S.bodies) - 4, "H1, B1, H2 and H3"


def test_f1_pair_columns_without_built_columns():
    from deckfill.sample_plan import build, two_dest

    info = read_template((FIX / NAME).read_bytes(), NAME)
    S = next(x for x in info.samples if x.id == "s9")
    assert two_dest(S) is None and "two" in S.classes
    built = build(S, parse_outline("## 預算\n- 科技 350 萬\n||\n- 科技佔 44%\n").slides[0])
    assert built.pairs and not built.merged, "the pair columns, never the merge"
    heads = [bf for bf in built.parts[0].boxes if bf.role == "head"]
    assert [bf.sid for bf in heads] == [911, 912], "the left column to H1, the right to H2, in x order"
    merged = build(S, parse_outline("## 預算\n- 科技 350 萬\n||\n- 科技佔 44%\n").slides[0], merge=True)
    assert merged.merged and not merged.pairs, "an explicit merge stays a merge"


def test_f4_c23_rejects_geometry_from_a_non_pair():
    """Codex's repro: box 1011 widened to the union with 1012 (equal size, disjoint, 150 pt below) as if it were a
    T5 heading: C23 must report it, since T5 never pairs them."""
    import io
    import zipfile

    data = (FIX / NAME).read_bytes()
    parts = parts_of(data)
    name = slides(parts)[9]
    root = xml(parts[name])
    sp = next(e for e in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp")
              if e.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr").get("id") == "1011")
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    xf = sp.find(".//" + ns + "xfrm")
    xf.find(ns + "ext").set("cx", str(800 * 12700))  # union x 100 to 900 pt
    xf.find(ns + "ext").set("cy", str(210 * 12700))  # from 1011's top to 1012's top
    from lxml import etree

    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            z.writestr(info, etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                       if info.filename == name else zin.read(info.filename))
    diffs = look_diff(buf.getvalue(), data)
    assert any("1011" in d for d in diffs), diffs


# rev 9 QA round 2 ----------------------------------------------------------------------------------


def test_r2_condensed_estimate_catches_the_orphan():
    """The 0.55 em estimate shows no orphan ("800 萬" on line 2) but the condensed 0.45 em one leaves 萬 alone, so the
    title steps down: 57 pt (0.55: 萬 alone, 473.1 pt), 54 pt (448.2 pt), 51 pt (423.3 pt) all leave it alone; at 48 pt
    both widths set one line (398.4 and 369.6 pt): written 4800."""
    from deckfill.plan import CONDENSED_EM, LATIN_EM
    from deckfill.sample_plan import last_line

    data, info, plan, out = run(FIX / NAME, "# Deck\n\n## 預算 港幣 800 萬\n- Body\n", {1: "s11"})
    S = next(x for x in info.samples if x.id == "s11")
    f = S.box(1101).fit_at(None, 6000, 6000)
    items = (Item(1, "預算 港幣 800 萬"),)
    assert last_line(items, f, LATIN_EM) == (2, 4), "0.55 em: no orphan"
    assert last_line(items, f, CONDENSED_EM) == (2, 1), "0.45 em: 萬 alone"
    t = next(bf for bf in plan.slides[1].boxes if bf.role == "title")
    assert t.sizes[0] == 4800 and t.box is None
    assert look_diff(out, data) == []


# Codex rev 9 round 2 ----------------------------------------------------------------------------------


def test_r2_1_warned_normal_title_never_beats_a_fitting_display_title():
    """sample-rank-floor: s2's 60 pt title is over at its 42 pt floor (warned); s3's 120 pt display title fits at step
    10 (60 pt). The automatic choice is s3, though s2 comes first in file order."""
    _, _, plan, _ = run(FIX / "sample-rank-floor.pptx", "# Deck\n\n## ABCDEFGHIJ\n- Body text\n")
    assert plan.chosen[1] == "s3"
    t = next(bf for bf in plan.slides[1].boxes if bf.role == "title")
    assert t.status == "shrunk" and t.sizes[0] == 6000


def test_r2_2_orphan_steps_count_in_the_ranking():
    """sample-rank-orphan: s2 writes 預算 港幣 800 萬 at 54 pt (two orphan steps from a full-size fit), s3 at 57 pt (one
    shrink step). The automatic choice is s3, though s2 comes first in file order."""
    from deckfill.sample_plan import build

    data, info, plan, _ = run(FIX / "sample-rank-orphan.pptx", "# Deck\n\n## 預算 港幣 800 萬\n- Body text\n")
    by = {x.id: x for x in info.samples}
    s = plan.outline.slides[1]
    assert build(by["s2"], s).parts[0].boxes[0].sizes[0] == 5400
    assert build(by["s3"], s).parts[0].boxes[0].sizes[0] == 5700
    assert plan.chosen[1] == "s3"


def test_r2_3_c23_rejects_pair_geometry_without_a_complete_pair_group():
    """r12: two heading and body pairs and a third B with no heading in their slot group. The reader finds no pair
    group; heading 1211 grown to its pair's content box (x 100, y 300, 300 by 60 pt) must be reported by C23."""
    import io
    import zipfile

    from lxml import etree

    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    assert next(x for x in info.samples if x.id == "s12").pair_groups == ()
    parts = parts_of(data)
    name = slides(parts)[11]
    root = xml(parts[name])
    sp = next(e for e in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp")
              if e.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr").get("id") == "1211")
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    sp.find(".//" + ns + "xfrm").find(ns + "ext").set("cy", str(60 * 12700))  # from H's top to B's top
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for zi in zin.infolist():
            z.writestr(zi, etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                       if zi.filename == name else zin.read(zi.filename))
    diffs = look_diff(buf.getvalue(), data)
    assert any("1211" in d for d in diffs), diffs
