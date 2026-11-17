"""Rev 9 fixture templates (spec map rev 6): sample-latin-font (C39, C40), sample-ghost and sample-ghostd11 (C41,
C42), sample-pairs (C43), sample-titlegrow (C44).

Every shape a test or golden names gets a fixed shape id (slide k uses ids k*100 + n), so the goldens are written by
hand from the spec, never from the planner. Called by make_fixtures.main() and by tests/conftest.py when missing.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree
from pptx.util import Emu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from make_sample_fixtures import M, SH, SW, bg, blank_slide, group, layout_named, new_prs, pic, q, rect, save, set_id, tb  # noqa: E402

PT = 12700
WIDE = (18288000, 10287000)  # 1440 by 810 pt, Marco's Canva deck


def E(v) -> int:
    return int(round(v * PT))


def wide_prs():
    prs = new_prs()
    prs.slide_width, prs.slide_height = Emu(WIDE[0]), Emu(WIDE[1])
    return prs


def tbp(shapes, sid, x, y, w, h, lines, pt, **kw):
    """tb in points."""
    return tb(shapes, sid, E(x), E(y), E(w), E(h), lines, pt, **kw)


def _rprs(shape):
    return list(shape._element.iter(q("a:rPr")))


def _color(alpha=None, rgb="FFFFFF"):
    f = etree.Element(q("a:solidFill"))
    c = etree.SubElement(f, q("a:srgbClr"), val=rgb)
    if alpha is not None:
        etree.SubElement(c, q("a:alpha"), val=str(alpha))
    return f


def run_props(shape, latin=None, ea=None, spc=None, b=None, i=None, alpha=None, rgb=None):
    """Set run properties on every run of a shape, children in schema order (fill, latin, ea)."""
    for r in _rprs(shape):
        for k, v in (("spc", spc), ("b", b), ("i", i)):
            if v is not None:
                r.set(k, str(v))
        if alpha is not None or rgb is not None:
            r.insert(0, _color(alpha, rgb or "FFFFFF"))
        if latin is not None:
            etree.SubElement(r, q("a:latin"), typeface=latin)
        if ea is not None:
            etree.SubElement(r, q("a:ea"), typeface=ea)


def line(shape, pts=None, pct=None):
    """a:lnSpc on every paragraph."""
    for p in shape._element.iter(q("a:p")):
        ppr = p.find(q("a:pPr"))
        if ppr is None:
            ppr = etree.Element(q("a:pPr"))
            p.insert(0, ppr)
        ln = etree.Element(q("a:lnSpc"))
        if pts is not None:
            etree.SubElement(ln, q("a:spcPts"), val=str(pts))
        else:
            etree.SubElement(ln, q("a:spcPct"), val=str(pct))
        ppr.insert(0, ln)


def lst(shape, level, xml):
    """The box's own a:lstStyle level element, from an XML fragment in the a namespace."""
    tx = shape._element.find(q("p:txBody"))
    ls = tx.find(q("a:lstStyle"))
    el = etree.fromstring('<a:lvl%dpPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" %s' % (level, xml))
    ls.append(el)


def zip_edit(path: Path, name: str, fn) -> None:
    data = path.read_bytes()
    zin = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            b = zin.read(info.filename)
            if info.filename == name:
                b = fn(b)
            z.writestr(info, b)
    path.write_bytes(buf.getvalue())


# ---------------------------------------------------------------------------------------------
# C39, C40


def make_latin_font(out):
    """s1 cover: display title in Anton (latin and ea) with spc -1455 and spcPts at 85% of its size; a 12 pt
    subtitle in Montserrat. s2: Anton title; 12 pt body in Arial Unicode MS (covers Chinese) with spcPct 85%. s3: body
    naming +mn-lt and +mn-ea, the theme's minor East Asian face being PingFang TC. s4: title naming 微軟正黑體 in
    a:ea; body with no named face (the presentation's default text style names none). s5: title whose list style
    sets spc, i and spcPts on level 1 (the run sets only the face); body in Montserrat with level-2 properties of its
    own (spcPts 1020, 12 pt). s6: a 20 pt body in a short box with spcPts 1700 (shrinks)."""
    prs = new_prs()
    dts = prs.part._element.find(q("p:defaultTextStyle"))
    for d in dts.iter(q("a:defRPr")):
        for t in ("latin", "ea", "cs"):
            for e in d.findall(q("a:" + t)):
                d.remove(e)
    s1 = blank_slide(prs, (110, 0, 15))
    t = tb(s1.shapes, 101, 600000, 1200000, 10 * M, 2200000, "PITCH DECK", 60)
    run_props(t, latin="Anton", ea="Anton", spc=-1455)
    line(t, pts=5100)
    sub = tb(s1.shapes, 111, 600000, 4200000, 8 * M, 600000, "Strategic consulting", 12)
    run_props(sub, latin="Montserrat", ea="Montserrat")
    pic(s1.shapes, 121, 10 * M, 5 * M, M, M, (200, 60, 60))

    s2 = blank_slide(prs, (250, 230, 230))
    t = tb(s2.shapes, 201, 600000, 400000, 10900000, 1200000, "PROBLEM", 44)
    run_props(t, latin="Anton", ea="Anton", spc=-500)
    line(t, pts=3740)
    b = tb(s2.shapes, 211, 600000, 1800000, 10900000, 3500000, "Body text", 12)
    run_props(b, latin="Arial Unicode MS", ea="Arial Unicode MS")
    line(b, pct=85000)

    s3 = blank_slide(prs, (230, 250, 230))
    t = tb(s3.shapes, 301, 600000, 400000, 10900000, 1200000, "THEME", 44)
    run_props(t, latin="Anton", ea="Anton")
    b = tb(s3.shapes, 311, 600000, 1800000, 10900000, 3500000, "Theme body", 14)
    run_props(b, latin="+mn-lt", ea="+mn-ea")

    s4 = blank_slide(prs, (230, 230, 250))
    t = tb(s4.shapes, 401, 600000, 400000, 10900000, 1200000, "FONTS", 44)
    run_props(t, latin="Anton", ea="微軟正黑體")
    tb(s4.shapes, 411, 600000, 1800000, 10900000, 3500000, "No face body", 14)

    s5 = blank_slide(prs, (250, 250, 220))
    t = tb(s5.shapes, 501, 600000, 400000, 10900000, 1200000, "STYLES", 44)
    run_props(t, latin="Anton", ea="Anton")
    lst(t, 1, '><a:lnSpc><a:spcPts val="3740"/></a:lnSpc><a:defRPr spc="-800" i="1"/></a:lvl1pPr>')
    b = tb(s5.shapes, 511, 600000, 1800000, 10900000, 3500000, "Level body", 14)
    run_props(b, latin="Montserrat", ea="Montserrat")
    line(b, pts=1190)
    lst(b, 2, 'marL="457200" lvl="1"><a:lnSpc><a:spcPts val="1020"/></a:lnSpc><a:defRPr sz="1200"/></a:lvl2pPr>')

    s6 = blank_slide(prs, (220, 250, 250))
    t = tb(s6.shapes, 601, 600000, 400000, 10900000, 1200000, "SHRINK", 44)
    run_props(t, latin="Anton", ea="Anton")
    line(t, pts=3740)
    b = tb(s6.shapes, 611, 600000, 1800000, 5 * M, 600000, "Short box", 20)
    run_props(b, latin="Montserrat", ea="Montserrat")
    line(b, pts=1700)
    path = save(prs, out, "sample-latin-font.pptx")

    def theme(blob: bytes) -> bytes:
        s = blob.decode("utf-8")
        i = s.index("<a:minorFont>")
        j = s.index('<a:ea typeface=""/>', i)
        return (s[:j] + '<a:ea typeface="PingFang TC"/>' + s[j + len('<a:ea typeface=""/>'):]).encode("utf-8")

    zip_edit(path, "ppt/theme/theme1.xml", theme)
    return path


# ---------------------------------------------------------------------------------------------
# C41, C42


def ghost(shapes, sid, x, y, w, h, text, pt, alpha):
    s = tb(shapes, sid, x, y, w, h, text, pt)
    run_props(s, alpha=alpha)
    return s


def make_ghost(out):
    """g1 cover: the real title (60 pt) under a 72 pt ghost at 15% alpha whose text equals it once normalised, a
    30% ghost with other text, a subtitle. g2: a title starting at a negative x with an equal ghost; a body crossing
    the right and bottom edges; boxes wholly on the slide setting the content margins. g3: a body crossing the bottom
    edge whose clamp would leave less than a line. g4: a body crossing the right edge inside a group with a picture
    sibling. g5: a short body under an equal ghost (continuations echo the suffix). g6: the 40% and 41% boxes, a box
    mixing a 15% run with an opaque one, and a box whose 20% alpha comes from its list style. g7: a small body whose
    R3 growth runs into an echo's area."""
    prs = new_prs()
    g1 = blank_slide(prs, (110, 0, 15))
    tb(g1.shapes, 101, 600000, 1100000, 6 * M, 1600000, "PITCH DECK", 60)
    ghost(g1.shapes, 102, 5 * M, 2500000, 6500000, 2 * M, "Pitch  deck!", 72, 15000)
    ghost(g1.shapes, 103, 600000, 4500000, 5 * M, 800000, "BACKDROP", 40, 30000)
    tb(g1.shapes, 111, 600000, 3300000, 5 * M, 500000, "Strategic consulting", 16)

    g2 = blank_slide(prs, (110, 0, 15))
    tb(g2.shapes, 201, -900000, 400000, 9 * M, 1200000, "SEE YOU", 54)
    ghost(g2.shapes, 202, -900000, 1900000, 9 * M, 1200000, "SEE YOU", 54, 15000)
    tb(g2.shapes, 211, 6 * M, 4500000, 7 * M, 2800000, "Contact us", 18)
    tb(g2.shapes, 221, 600000, 6 * M, M, 400000, "2025", 14)
    tb(g2.shapes, 231, 600000, 3200000, 4 * M, 500000, "Phone", 14)
    tb(g2.shapes, 232, 8 * M, 3200000, 3600000, 500000, "Email", 14)

    g3 = blank_slide(prs, (240, 230, 220))
    tb(g3.shapes, 301, 600000, 400000, 10 * M, M, "Short box", 40)
    tb(g3.shapes, 311, 600000, 6700000, 6 * M, M, "Body", 20)
    tb(g3.shapes, 312, 7 * M, 6550000, 4 * M, 250000, "Note", 12)

    g4 = blank_slide(prs, (220, 230, 240))
    tb(g4.shapes, 401, 600000, 400000, 10 * M, M, "Grouped", 40)

    def kids(sh):
        tb(sh, 411, 0, 0, 6 * M, 1500000, "Inside", 20)
        pic(sh, 412, 0, 1600000, M, 500000, (40, 90, 160))
    group(g4.shapes, 410, (7 * M, 2 * M), (6 * M, 2100000), (6 * M, 2100000), kids)
    tb(g4.shapes, 421, 600000, 6 * M, 2 * M, 300000, "Tag", 12)

    g5 = blank_slide(prs, (230, 240, 220))
    tb(g5.shapes, 501, 600000, 300000, 10 * M, 900000, "Long list", 40)
    ghost(g5.shapes, 502, 3 * M, 3 * M, 9 * M, 1500000, "LONG LIST", 60, 20000)
    tb(g5.shapes, 511, 600000, 1400000, 5 * M, 1200000, "Body", 18)

    g6 = blank_slide(prs, (240, 240, 240))
    tb(g6.shapes, 601, 600000, 300000, 10 * M, 900000, "Marks", 40)
    tb(g6.shapes, 611, 600000, 1400000, 6 * M, 2 * M, "Body text", 18)
    ghost(g6.shapes, 621, 7 * M, 1400000, 4 * M, 500000, "Mark forty", 20, 40000)
    ghost(g6.shapes, 622, 7 * M, 2 * M, 4 * M, 500000, "Mark fortyone", 20, 41000)
    mixed = tb(g6.shapes, 623, 7 * M, 2600000, 4 * M, 500000, "Mixed ", 20)
    p = mixed.text_frame.paragraphs[0]
    r2 = p.add_run()
    r2.text = "run"
    from pptx.util import Pt
    r2.font.size = Pt(20)
    rprs = _rprs(mixed)
    rprs[0].insert(0, _color(15000))
    rprs[1].insert(0, _color(None))
    inh = tb(g6.shapes, 624, 7 * M, 3200000, 4 * M, 500000, "Inherited mark", 20)
    lst(inh, 1, '><a:defRPr><a:solidFill><a:srgbClr val="000000"><a:alpha val="20000"/></a:srgbClr></a:solidFill></a:defRPr></a:lvl1pPr>')

    g7 = blank_slide(prs, (250, 245, 235))
    tb(g7.shapes, 701, 600000, 300000, 10900000, 900000, "Grow", 40)
    tb(g7.shapes, 711, 600000, 1700000, 3 * M, M, "Body", 16)
    ghost(g7.shapes, 702, 4 * M, 1700000, 7 * M, 4 * M, "GROW", 60, 10000)
    return save(prs, out, "sample-ghost.pptx")


def make_ghost_d11(out):
    """D11 with T3: sample slides on the Title and Content placeholders (no slide background of their own); two of
    the three carry a free ghost text box (15% alpha, equal to the title) with an opaque box fill over 30% of the
    slide. Ghosts never count toward the design test, so the default stays layout."""
    prs = new_prs()
    lay = layout_named(prs, "Title and Content")
    for k in (1, 2, 3):
        s = prs.slides.add_slide(lay)
        s.shapes.title.text = f"Plan {k}"
        set_id(s.shapes.title, k * 100 + 1)
        body = next(sp for sp in s.placeholders if sp.placeholder_format.idx == 1)
        body.text = f"Body {k}"
        set_id(body, k * 100 + 11)
        if k < 3:
            g = ghost(s.shapes, k * 100 + 21, M, 2 * M, 8 * M, 3 * M, f"Plan {k}", 80, 15000)
            g.fill.solid()
            from pptx.dml.color import RGBColor
            g.fill.fore_color.rgb = RGBColor(230, 230, 250)
    return save(prs, out, "sample-ghostd11.pptx")


# ---------------------------------------------------------------------------------------------
# C43 (1440 by 810 pt)


def _pairs(sl, base, hs, bs, hpt, bpt, labels=(), label_pt=23.5):
    """Heading and body boxes (ids base+11.., base+21..), number labels (base+31..) on square backings (base+41..)."""
    for n, (x, y, w, h) in enumerate(hs, start=1):
        tbp(sl.shapes, base + 10 + n, x, y, w, h, f"HEADING {n}", hpt)
    for n, (x, y, w, h) in enumerate(bs, start=1):
        tbp(sl.shapes, base + 20 + n, x, y, w, h, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.", bpt)
    for n, (text, (x, y)) in enumerate(labels, start=1):
        rect(sl.shapes, base + 40 + n, E(x), E(y), E(25), E(28), (255, 220, 225))
        tbp(sl.shapes, base + 30 + n, x, y, 25, 28, text, label_pt)


def make_pairs(out):
    """p1 Marco's Canva slide 2: three H and B pairs (23.5 pt over 12 pt) with 1. 2. 3. labels on square backings.
    p2 his slide 7: three pairs, no labels, H widths 223, 223 and 304 pt. p3 simple-business s7 (doubled): a horizontal
    and a stacked pair group sharing pair 2, B under the body bar. p4 business-conference s7: four slots of 32 pt
    headings and 24 pt bodies (slots qualify). p5 Marco's year template s5: three 36 pt and three 28 pt slots (slots
    qualify). p6 p1 with 01 02 03 labels and its third pair moved right so its body crosses the right edge (C42)."""
    prs = wide_prs()
    p1 = blank_slide(prs, (110, 0, 15))
    tbp(p1.shapes, 101, 70, 84, 1288, 187, "PROBLEM", 200)
    _pairs(p1, 100, [(81, 566, 188, 28), (532, 566, 187, 28), (983, 566, 229, 28)],
           [(81, 602, 375, 128), (532, 602, 375, 128), (983, 602, 375, 128)], 23.5, 12,
           labels=[("1.", (90, 516)), ("2.", (541, 516)), ("3.", (993, 516))])

    p2 = blank_slide(prs, (250, 220, 225))
    tbp(p2.shapes, 201, 70, 84, 770, 357, "MARKET STRATEGY", 200)
    _pairs(p2, 200, [(81, 573, 223, 55), (524, 573, 223, 55), (967, 573, 304, 55)],
           [(81, 643, 391, 85), (524, 643, 391, 85), (967, 643, 391, 85)], 23.5, 12)

    p3 = blank_slide(prs, (245, 240, 230))
    tbp(p3.shapes, 301, 80, 460, 620, 300, "WRITE YOUR TOPIC", 124)
    _pairs(p3, 300, [(80, 110, 218, 52), (768, 110, 218, 52), (768, 474, 218, 58)],
           [(80, 198, 580, 168), (768, 198, 606, 168), (768, 562, 606, 168)], 24, 12)

    p4 = blank_slide(prs, (230, 235, 250))
    tbp(p4.shapes, 401, 81, 86, 1278, 90, "Implementation plan", 80)
    tbp(p4.shapes, 404, 81, 195, 1005, 41, "Guide your audience", 30)
    xs = (81, 418, 756, 1094)
    _pairs(p4, 400, [(x, 505, 264, 39) for x in xs], [(x, 568, 264, 96) for x in xs], 32, 24)

    p5 = blank_slide(prs, (235, 250, 235))
    tbp(p5.shapes, 501, 359, 133, 721, 290, "My Top 3", 120)
    xs = (81, 547, 1013)
    _pairs(p5, 500, [(x, 527, 345, 43) for x in xs], [(x - 3, 598, 351, 95) for x in xs], 36, 28)

    p6 = blank_slide(prs, (110, 0, 15))
    tbp(p6.shapes, 601, 70, 84, 1288, 187, "PROBLEM", 200)
    _pairs(p6, 600, [(81, 566, 188, 28), (532, 566, 187, 28), (1100, 566, 229, 28)],
           [(81, 602, 375, 128), (532, 602, 375, 128), (1100, 602, 375, 128)], 23.5, 12,
           labels=[("01", (90, 516)), ("02", (541, 516)), ("03", (1110, 516))])
    return save(prs, out, "sample-pairs.pptx")


# ---------------------------------------------------------------------------------------------
# C44 (1440 by 810 pt)


def make_titlegrow(out):
    """t1 the Canva cover: a 297 pt title box with free space to its right, a logo in the top-right corner, a 29 pt
    subtitle bottom right, a 15% ghost equal to the title. t2 a 200 pt title box whose right part lies under a logo
    (a narrower rectangle wins). t3 a title that fits at full size. t4 an 80 pt title (never past 70%). t5 a 120 pt
    title in open space (ties go to the larger area). t6 a title over two qualifying backings (no growth). t7 a
    grouped title with a picture sibling. t8 a title beside a pair group whose B reaches left of its H (the H's final
    union takes cells)."""
    prs = wide_prs()
    t1 = blank_slide(prs, (110, 0, 15))
    tbp(t1.shapes, 101, 70, 110, 649, 530, "PITCH DECK", 297)
    pic(t1.shapes, 102, E(1300), E(40), E(60), E(60), (250, 220, 225))
    tbp(t1.shapes, 111, 944, 702, 416, 31, "STRATEGIC CONSULTING", 29)
    ghost(t1.shapes, 103, E(868), E(275), E(730), E(596), "PITCH DECK", 334, 15000)

    t2 = blank_slide(prs, (250, 220, 225))
    tbp(t2.shapes, 201, 70, 84, 1300, 300, "MARKET STRATEGY", 200)
    pic(t2.shapes, 202, E(1100), E(60), E(150), E(150), (110, 0, 15))
    tbp(t2.shapes, 211, 81, 600, 600, 100, "Body", 20)

    t3 = blank_slide(prs, (110, 0, 15))
    tbp(t3.shapes, 301, 70, 84, 1300, 300, "OK", 200)
    tbp(t3.shapes, 311, 81, 600, 600, 100, "Body", 20)

    t4 = blank_slide(prs, (230, 235, 250))
    tbp(t4.shapes, 401, 81, 86, 600, 90, "Implementation plan", 80)
    tbp(t4.shapes, 411, 81, 400, 800, 200, "Body", 24)

    t5 = blank_slide(prs, (235, 250, 235))
    tbp(t5.shapes, 501, 100, 100, 400, 150, "OPEN", 120)
    tbp(t5.shapes, 511, 100, 650, 500, 80, "Body", 20)

    t6 = blank_slide(prs, (250, 245, 235))
    rect(t6.shapes, 602, E(60), E(70), E(340), E(170), (255, 255, 255))
    rect(t6.shapes, 603, E(65), E(75), E(330), E(160), (250, 250, 250))
    tbp(t6.shapes, 601, 70, 80, 300, 150, "BACKED", 120)
    tbp(t6.shapes, 611, 81, 600, 600, 100, "Body", 20)

    t7 = blank_slide(prs, (240, 240, 250))

    def kids(sh):
        tbp(sh, 701, 0, 0, 500, 200, "GROUPED", 150)
        pic(sh, 702, E(520), 0, E(180), E(180), (110, 0, 15))
    group(t7.shapes, 710, (E(70), E(84)), (E(700), E(300)), (E(700), E(300)), kids)
    tbp(t7.shapes, 711, 81, 600, 600, 100, "Body", 20)

    t8 = blank_slide(prs, (245, 235, 240))
    tbp(t8.shapes, 801, 70, 84, 500, 200, "BESIDE", 150)
    tbp(t8.shapes, 811, 900, 500, 200, 40, "HEADING 1", 24)
    tbp(t8.shapes, 821, 500, 550, 600, 60, "Body one", 12)
    tbp(t8.shapes, 812, 900, 640, 200, 40, "HEADING 2", 24)
    tbp(t8.shapes, 822, 500, 690, 600, 60, "Body two", 12)
    return save(prs, out, "sample-titlegrow.pptx")


# ---------------------------------------------------------------------------------------------
# C46 (rev 9 QA round 1, 1440 by 810 pt)


def line_frame(shapes, sid, x, y, w, h):
    """Canva's caption frame: a four-corner custGeom rectangle with a line and no fill element at all (Marco's s6
    shapes 6, 11 and 15)."""
    from make_sample_fixtures import custrect

    s = custrect(shapes, sid, x, y, w, h, (0, 0, 0))
    pr = s._element.find(q("p:spPr"))
    pr.remove(pr.find(q("a:solidFill")))
    pr.remove(pr.find(q("a:ln")))
    ln = etree.SubElement(pr, q("a:ln"), w="19050")
    ln.append(_color(rgb="70020F"))
    s._element.remove(s._element.find(q("p:style")))  # Canva writes no theme style reference
    return s


def framed_caption(shapes, gid, x, y, w, h, cap_sid, cap):
    """A group holding a line-only frame and an invisible rectangle (no fill, no line), as Canva exports it, with a
    24 pt caption text box over the frame's middle."""
    def kids(sh):
        line_frame(sh, gid + 1, 0, 0, E(w), E(h))
        r = rect(sh, gid + 2, 0, 0, E(w), E(h), (0, 0, 0))
        pr = r._element.find(q("p:spPr"))
        pr.remove(pr.find(q("a:solidFill")))
        pr.remove(pr.find(q("a:ln")))
        r._element.remove(r._element.find(q("p:style")))
    group(shapes, gid, (E(x), E(y)), (E(w), E(h)), (E(w), E(h)), kids)
    tbp(shapes, cap_sid, x + 40, y + h / 2 - 20, w - 80, 40, cap, 24)


def make_round1(out):
    """r1 Q9-1: elegant-pitch-deck's cover at twice its size: an 80 pt "P" box over the top-left edges (larger in area
    than the subtitle box, and T4 cannot clamp it: the left margin, 658 pt, lies right of its right edge), a 120 pt
    title, a 40 pt subtitle box and a 32 pt caption. r2 Q9-3: a 60 pt title box 450 pt wide inside its insets, where
    預算 港幣 800 萬 leaves 萬 alone on line 2 at 100% and 95% and sets one line at 90%. r3 Q9-3: a 60 pt title box
    2.05 em wide inside its insets that holds two lines only at the 70% floor, so three glyphs always leave one alone
    on line 2; a picture to its right and the body below take the cells T6 could grow into. r4 Q9-4: two Canva caption
    frames (a line-only custGeom frame and an invisible rectangle in a group) behind captions the fill clears, one at
    2.6% of the slide (a backing under Q1's size rule) and one at 9.1% (stays). r5 Q9-1: the only body box crosses the
    bottom edge and T4 cannot clamp it (the bottom margin, 650 pt, lies above its top): no other candidate remains, so
    it keeps its sample box with check-this-slide."""
    prs = wide_prs()
    r1 = blank_slide(prs, (250, 245, 240))
    tbp(r1.shapes, 101, -20, -52, 242, 312, "P", 80)
    tbp(r1.shapes, 102, 658, 134, 656, 290, "ELEGANT PITCH", 120)
    tbp(r1.shapes, 111, 710, 470, 480, 140, "Subtitle here", 40)
    tbp(r1.shapes, 112, 988, 676, 298, 40, "Presentation 2024", 32)

    r2 = blank_slide(prs, (245, 240, 250))
    tbp(r2.shapes, 201, 100, 60, 464.4, 160, "Title", 60)
    tbp(r2.shapes, 211, 100, 300, 1200, 400, "Body", 24)

    r3 = blank_slide(prs, (240, 250, 245))
    tbp(r3.shapes, 301, 100, 60, 137.4, 109.2, "Title", 60)
    pic(r3.shapes, 302, E(230), E(40), E(1100), E(100), (110, 0, 15))
    tbp(r3.shapes, 311, 100, 170, 1200, 500, "Body", 24)

    r4 = blank_slide(prs, (250, 250, 240))
    tbp(r4.shapes, 401, 100, 60, 800, 100, "TEAM UPDATE", 60)
    framed_caption(r4.shapes, 410, 300, 600, 300, 100, 415, "CAPTION ONE")
    framed_caption(r4.shapes, 420, 800, 300, 560, 190, 425, "CAPTION TWO")

    r5 = blank_slide(prs, (240, 245, 250))
    tbp(r5.shapes, 501, 100, 60, 800, 100, "ONLY BODY", 60)
    tbp(r5.shapes, 511, 100, 760, 600, 100, "Body", 24)

    # Codex rev 9 round 1 E1: a 120 pt display title (12% of 810 pt is 97.2 pt) crossing the left edge whose clamped
    # box (x from 100 pt, the body's left) is 87.2 pt tall: 80 pt inside its insets, a 60 pt line (72 pt) at T6's 50%
    # floor but not an 84 pt one (100.8 pt) at 70%
    r6 = blank_slide(prs, (245, 250, 240))
    tbp(r6.shapes, 601, -20, 200, 900, 87.2, "DISPLAY", 120)
    tbp(r6.shapes, 611, 100, 500, 1000, 200, "Body", 24)

    # Codex rev 9 round 1 F2: 120 pt display titles for a 5.5 em one-word title, 110 pt tall inside their insets
    # (one line only): r7 340 pt wide inside (fits at step 10, 60 pt), r8 440 pt (step 7, 78 pt); a picture right
    # of each title and the body just below take the cells T6 could grow into
    for sl_id, w in ((7, 340), (8, 440)):
        sl = blank_slide(prs, (240, 240, 240))
        tbp(sl.shapes, sl_id * 100 + 1, 100, 60, w + 14.4, 117.2, "Title", 120)
        pic(sl.shapes, sl_id * 100 + 2, E(100 + w + 14.4 + 1), E(40), E(200), E(200), (110, 0, 15))
        tbp(sl.shapes, sl_id * 100 + 11, 100, 178.2, 1200, 400, "Body", 24)

    # Codex rev 9 round 1 F1: three identical heading and body pairs in a row: no 2-slot group and six body boxes, so
    # the sample has no built column destination, but its pair group gives two columns
    r9 = blank_slide(prs, (250, 240, 240))
    tbp(r9.shapes, 901, 100, 60, 1000, 100, "Title", 60)
    for k, x in enumerate((100, 520, 940), start=1):
        tbp(r9.shapes, 910 + k, x, 300, 380, 60, f"Heading {k}", 32)
        tbp(r9.shapes, 920 + k, x, 380, 380, 200, f"Body {k}", 20)

    # Codex rev 9 round 1 F4: two equal-size, horizontally disjoint boxes 150 pt apart, never a T5 pair
    r10 = blank_slide(prs, (240, 250, 250))
    tbp(r10.shapes, 1001, 100, 60, 1000, 100, "Title", 60)
    tbp(r10.shapes, 1011, 100, 300, 300, 60, "Left", 24)
    tbp(r10.shapes, 1012, 600, 510, 300, 60, "Right", 24)

    # rev 9 QA round 2 (flag 2): a 60 pt title box 420 pt wide inside its insets. At 0.55 em "預算 港幣 800 萬" breaks
    # before "800 " (438 pt) and sets "800 萬" on line 2; at the condensed 0.45 em "800 " fits (402 pt) and 萬 is alone
    r11 = blank_slide(prs, (250, 245, 245))
    tbp(r11.shapes, 1101, 100, 60, 434.4, 160, "Title", 60)
    tbp(r11.shapes, 1111, 100, 300, 1200, 400, "Body", 24)

    # Codex rev 9 round 2 R2-3: two heading and body pairs and a third B with no heading in the same slot group (same
    # size, width and top): the reader finds no pair group, so no T5 geometry is allowed
    r12 = blank_slide(prs, (245, 245, 250))
    tbp(r12.shapes, 1201, 100, 60, 1000, 100, "Title", 60)
    for k, x in enumerate((100, 500), start=1):
        tbp(r12.shapes, 1210 + k, x, 300, 300, 50, f"Heading {k}", 32)
    for k, x in enumerate((100, 500, 900), start=1):
        tbp(r12.shapes, 1220 + k, x, 360, 300, 100, f"Body {k}", 20)
    return save(prs, out, "sample-round1.pptx")


def _rank_deck(out, name, samples):
    """A cover (a title and nothing else, so never a content candidate) and content samples, each a title box with a
    picture right of it and its body just below, so T6 cannot grow the title: samples are (title pt, inner width,
    inner height) in points."""
    prs = wide_prs()
    c = blank_slide(prs, (110, 0, 15))
    tbp(c.shapes, 101, 100, 300, 1200, 200, "COVER", 60)
    for k, (pt, w, h) in enumerate(samples, start=2):
        sl = blank_slide(prs, (240, 240, 240))
        tbp(sl.shapes, k * 100 + 1, 100, 60, w + 14.4, h + 7.2, "Title", pt)
        pic(sl.shapes, k * 100 + 2, E(100 + w + 14.4 + 1), E(40), E(200), E(100), (110, 0, 15))
        tbp(sl.shapes, k * 100 + 11, 100, 60 + h + 7.2 + 1, 1200, 400, "Body", 24)
    return save(prs, out, name)


def make_rank(out):
    """Codex rev 9 round 2. sample-rank-floor (R2-1): s2 a 60 pt title 200 by 60 pt inside its insets, where a 5.5 em
    one-word title is over even at its 42 pt floor (231 pt wide, two lines); s3 a 120 pt display title 340 by 110 pt
    inside, where it fits at step 10 (60 pt, 330 pt). sample-rank-orphan (R2-2): s2 r2's box (450 by 152.8 pt inside),
    where 預算 港幣 800 萬 fits at 60 pt but leaves 萬 alone until 54 pt; s3 480 by 100 pt inside, where it fits one
    line at 57 pt (473.1 pt) and not at 60 pt (two lines, 144 pt)."""
    return [_rank_deck(out, "sample-rank-floor.pptx", [(60, 200, 60), (120, 340, 110)]),
            _rank_deck(out, "sample-rank-orphan.pptx", [(60, 450, 152.8), (60, 480, 100)])]


def make_all(out) -> list:
    return [make_latin_font(out), make_ghost(out), make_ghost_d11(out), make_pairs(out), make_titlegrow(out),
            make_round1(out)] + make_rank(out)


if __name__ == "__main__":
    for p_ in make_all(HERE / "out"):
        print(p_)
