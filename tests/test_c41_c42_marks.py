"""C41 (watermarks, T3) and C42 (edge clamp, T4) on sample-ghost and sample-ghostd11.

C41: the anchor is the real title, never a ghost; an equal ghost echoes the written title at its own size with
wrapping off (a continuation's echo carries the suffix: the C24 golden 'ghost'); an unequal ghost is cleared; ghosts
take no grid cells and do not change D11's default; 40% is a watermark and 41% is not; a box mixing a 15% run with an
opaque run is not; opacity from a:lstStyle counts. C42: destinations crossing a slide edge are pulled to the content
margin, echoes keep their bleed, a clamp inside a group keeps its sibling's box, a clamp that would leave less than a
line falls back to the sample box with check-this-slide. Expected boxes are computed by hand from the fixture."""

import io
import zipfile

from lxml import etree

from conftest import FIX, ROOT
from deckfill import fill, parse_outline, plan_deck, read_template
from sample_look import boxes, look_diff
from sample_oracle import a, golden, nv_id, p, parts_of, slides, text_lines, tree_of
from test_c24_c27_sample_text import GOLD, OUTLINES

NAME = "sample-ghost.pptx"
M = 1000000
SW, SH = 12192000, 6858000


def info_of(name=NAME):
    return read_template((FIX / name).read_bytes(), name)


def sample(info, sid):
    return next(S for S in info.samples if S.id == sid)


def run(text, ovr, name=NAME):
    data = (FIX / name).read_bytes()
    info = read_template(data, name)
    plan = plan_deck(info, parse_outline(text), ovr, route="sample")
    return data, info, plan, fill(data, name, plan)


def ghost_out():
    return run((OUTLINES / "ghost.md").read_text(encoding="utf-8"), {1: "s2", 2: "s5"})


def ghost_problems(info, plan, out: bytes) -> list[str]:
    """The fixture's C41 promises on the ghost outline's output."""
    bad = []
    want_title = {"s1": (101,), "s2": (201,), "s5": (501,), "s6": (601,), "s7": (701,)}
    for sid, t in want_title.items():
        if sample(info, sid).title != t:
            bad.append(f"{sid}: title region {sample(info, sid).title}, want {t} (a ghost must never anchor)")
    op = parts_of(out)
    names = slides(op)
    for n, ps in enumerate(plan.slides, start=1):
        tree = tree_of(op[names[n - 1]])
        by_id = {nv_id(el)[0]: el for el in tree.iter(p("sp"))}
        echo = {"s1": 102, "s2": 202, "s5": 502}.get(ps.layout)
        if echo is None:
            continue
        el = by_id.get(echo)
        if el is None:
            bad.append(f"slide {n}: echo {echo} missing")
            continue
        text = "".join(t.text or "" for t in el.iter(a("t")))
        if text != ps.title:
            bad.append(f"slide {n}: echo {echo} reads {text!r}, want the written title {ps.title!r}")
        if el.find(p("txBody")).find(a("bodyPr")).get("wrap") != "none":
            bad.append(f"slide {n}: echo {echo} wraps")
        if any(r.get("sz") not in (None, {102: "7200", 202: "5400", 502: "6000"}[echo]) for r in el.iter(a("rPr"))):
            bad.append(f"slide {n}: echo {echo} not at its own size")
    if 103 in {nv_id(el)[0] for name in names for el in tree_of(op[name]).iter(p("sp"))}:
        bad.append("the unequal ghost 103 survived")
    return bad


def test_c41_ghost_outline():
    _, info, plan, out = ghost_out()
    assert ghost_problems(info, plan, out) == []


def test_c41_thresholds():
    S = sample(info_of(), "s6")
    assert set(S.marks) == {621, 624}, "40% and an a:lstStyle 20% are watermarks; 41% and a mixed box are not"
    assert {622, 623} <= set(S.bodies)


def test_c41_ghosts_take_no_grid_cells():
    """g7: twelve bullets on a picked sample need 2 or more continuations, so its body grows (R3); the echo 702 sits in
    the free space beside the body and takes no cells, so the grown box reaches over it."""
    text = "# Grow deck\n\n## Grow\n" + "".join(f"- Point {i}\n" for i in range(12))
    _, info, plan, _ = run(text, {1: "s7"})
    body = next(bf for ps in plan.slides for bf in ps.boxes if bf.sid == 711)
    assert body.box is not None, "the body must grow"
    gx, gy, gcx, gcy = body.box
    ghost = (4 * M, 1700000, 7 * M, 4 * M)
    assert gx + gcx > ghost[0] + M, f"grown box {body.box} stops short of the ghost's area {ghost}"


def test_c41_ghosts_do_not_change_d11():
    info = info_of("sample-ghostd11.pptx")
    assert not any(S.design for S in info.samples)
    assert info.route == "layout"


# --- C42 ------------------------------------------------------------------------------------------------------------


def box_of_out(out, n, sid):
    op = parts_of(out)
    return boxes(tree_of(op[slides(op)[n - 1]]))[sid]


def clamp_problems(out) -> list[str]:
    bad = []
    want = {
        (2, 201): (600000, 400000, 7500000, 1200000),  # left side to the 0.6M margin, right edge kept
        (2, 202): (-900000, 1900000, 9 * M, 1200000),  # the echo keeps its bleed
        (2, 211): (6 * M, 4500000, 5600000, 1900000),  # right to 11.6M, bottom to 6.4M
    }
    for (n, sid), w in want.items():
        got = box_of_out(out, n, sid)
        if got != w:
            bad.append(f"slide {n} box {sid}: {got}, want {w}")
    return bad


def test_c42_clamps():
    _, _, _, out = ghost_out()
    assert clamp_problems(out) == []


def test_c42_group_clamp_keeps_sibling():
    data, _, plan, out = run("# Deck\n\n## Grouped\n- Inside text\n", {1: "s4"})
    body = box_of_out(out, 2, 411)
    assert body == (7 * M, 2 * M, 3600000, 1500000), body
    assert box_of_out(out, 2, 412) == (7 * M, 3600000, M, 500000)
    assert look_diff(out, data) == []


def test_c42_short_clamp_leaves_the_choice():
    # rev 9 QA round 1 Q9-1: box 311's clamp would hold less than a line, so it is not a candidate and the next body
    # box (312) takes the body role with no check; 311 is cleared at its sample box. The fallback with check, when no
    # other candidate remains, is test_c46_q91_only_body_keeps_check.
    _, _, plan, out = run("# Deck\n\n## Short box\n- Body text\n", {1: "s3"})
    bf = next(b for b in plan.slides[1].boxes if b.role == "body")
    assert bf.sid == 312 and bf.status != "check"
    assert "check" not in plan.slides[1].flags


# --- negative demos -------------------------------------------------------------------------------------------------


def test_c41_negative_ghost_anchor(monkeypatch):
    """Mutation: a watermark may be the anchor; the check fails."""
    import deckfill.sample as smp
    import deckfill.template as tpl

    tpl._cache.clear()  # read_template caches by the bytes: read again under the mutation
    monkeypatch.setattr(smp, "watermark", lambda sp, styles: False)
    try:
        _, info, plan, out = ghost_out()
        assert ghost_problems(info, plan, out) != []
    finally:
        tpl._cache.clear()


def _edit(out: bytes, n: int, fn) -> bytes:
    op = parts_of(out)
    target = slides(op)[n - 1]
    zin = zipfile.ZipFile(io.BytesIO(out))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            b = zin.read(info.filename)
            if info.filename == target:
                root = etree.fromstring(b)
                fn(root)
                b = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            z.writestr(info, b)
    return buf.getvalue()


def _shape(root, sid):
    return next(el for el in root.iter(p("sp")) if nv_id(el)[0] == sid)


def test_c41_negative_echo_left_with_sample_text():
    """An echo left with the sample's text: caught by C24's golden."""
    data, _, _, out = ghost_out()

    def back(root):
        for t in _shape(root, 102).iter(a("t")):
            t.text = "Pitch  deck!"
    got = text_lines(_edit(out, 1, back), data)
    assert got != golden(GOLD / "ghost.golden")


def test_c42_negative_unclamped_title():
    data, _, _, out = ghost_out()

    def unclamp(root):
        off = _shape(root, 201).find(p("spPr")).find(a("xfrm")).find(a("off"))
        off.set("x", "-900000")
        _shape(root, 201).find(p("spPr")).find(a("xfrm")).find(a("ext")).set("cx", str(9 * M))
    bad = _edit(out, 2, unclamp)
    assert clamp_problems(bad) != []


def test_c42_c23_rejects_an_undeclared_box():
    data, _, _, out = ghost_out()

    def shift(root):
        _shape(root, 211).find(p("spPr")).find(a("xfrm")).find(a("off")).set("x", "5000000")
    assert look_diff(_edit(out, 2, shift), data) != []
