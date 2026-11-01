"""Rev 8 fixture templates for the sample-slide route (spec map rev 5), made from python-pptx's default template.

Every shape a test or golden names gets a fixed shape id (slide k uses ids k*100 + n), so the goldens in
tests/goldens/sample/ are written by hand from D12, never from the planner. Called by make_fixtures.main().
"""

from __future__ import annotations

import copy
import io

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Emu, Pt

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
SW, SH = 12192000, 6858000
M = 1000000  # one "M" EMU, for readable coordinates


def q(name: str) -> str:
    p, local = name.split(":")
    return "{%s}%s" % (NS[p], local)


def new_prs():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(SW), Emu(SH)
    return prs


def layout_named(prs, name: str):
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == name:
                return lay
    raise KeyError(name)


def png(rgb, size=(60, 40)) -> io.BytesIO:
    b = io.BytesIO()
    Image.new("RGB", size, rgb).save(b, "PNG")
    b.seek(0)
    return b


def set_id(shape, sid: int, name: str | None = None) -> None:
    c = shape._element.find(".//" + q("p:cNvPr"))
    c.set("id", str(sid))
    c.set("name", name or f"S{sid}")


def bg(slide, rgb) -> None:
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(*rgb)


def tb(shapes, sid, x, y, w, h, lines, pt, fill=None, hidden=False):
    """A free text box: one paragraph per line, every run sized pt, wrapping on, no autofit."""
    s = shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    set_id(s, sid)
    tf = s.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = line
        r.font.size = Pt(pt)
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = RGBColor(*fill)
    if hidden:
        s._element.find(".//" + q("p:cNvPr")).set("hidden", "1")
    return s


def rect(shapes, sid, x, y, w, h, rgb):
    s = shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(x), Emu(y), Emu(w), Emu(h))
    set_id(s, sid)
    s.fill.solid()
    s.fill.fore_color.rgb = RGBColor(*rgb)
    s.line.fill.background()
    return s


def pic(shapes, sid, x, y, w, h, rgb, crop_left=None):
    s = shapes.add_picture(png(rgb), Emu(x), Emu(y), Emu(w), Emu(h))
    set_id(s, sid)
    if crop_left:
        s.crop_left = crop_left
    return s


def group(shapes, sid, off, ext, chext, build, rot=None):
    """A group whose children are laid out in child coordinates and scaled to ext (chOff 0, 0)."""
    g = shapes.add_group_shape()
    set_id(g, sid)
    build(g.shapes)
    pr = g._element.find(q("p:grpSpPr"))
    for old in pr.findall(q("a:xfrm")):
        pr.remove(old)
    xf = etree.Element(q("a:xfrm"))
    if rot:
        xf.set("rot", str(rot))
    etree.SubElement(xf, q("a:off"), x=str(off[0]), y=str(off[1]))
    etree.SubElement(xf, q("a:ext"), cx=str(ext[0]), cy=str(ext[1]))
    etree.SubElement(xf, q("a:chOff"), x="0", y="0")
    etree.SubElement(xf, q("a:chExt"), cx=str(chext[0]), cy=str(chext[1]))
    pr.insert(0, xf)
    return g


def save(prs, out, name):
    path = out / name
    prs.save(path)
    return path


def blank_slide(prs, rgb=None):
    s = prs.slides.add_slide(layout_named(prs, "Blank"))
    if rgb:
        bg(s, rgb)
    return s


# ---------------------------------------------------------------------------------------------


def make_sample_design(out):
    """Layouts with placeholders and no decoration; 8 sample slides with their own backgrounds, pictures and scaled
    groups: s1 a title split over four one-word boxes plus four year-digit labels, s2 a 3-slot row, s3 a second
    3-slot list of different slot sizes, s4 a two-box comparison, s5 a section slide, s6 a slide whose text says
    credit card, s7 a font-guide instruction slide with hex codes, s8 a thank-you slide."""
    prs = new_prs()
    s1 = blank_slide(prs, (250, 240, 225))
    pic(s1.shapes, 101, 7 * M, M // 2, 4 * M + 500000, 5 * M + 800000, (40, 90, 160), crop_left=0.1)
    for i, word in enumerate(("My", "Year", "In", "Review")):
        def kids(sh, word=word, i=i):
            rect(sh, 111 + 10 * i, 0, 0, 300000, 350000, (255, 255, 255))
            tb(sh, 112 + 10 * i, 0, 0, 300000, 350000, word, 40)
        group(s1.shapes, 110 + 10 * i, (600000 + 1400000 * i, 2 * M), (1200000, 1400000), (300000, 350000), kids)
    for i, digit in enumerate("2026"):
        def kids(sh, digit=digit, i=i):
            rect(sh, 151 + 10 * i, 0, 0, 125000, 125000, (240, 170, 60))
            tb(sh, 152 + 10 * i, 0, 0, 125000, 125000, digit, 28)
        group(s1.shapes, 150 + 10 * i, (600000 + 700000 * i, 3800000), (500000, 500000), (125000, 125000), kids)

    s2 = blank_slide(prs, (225, 240, 250))
    tb(s2.shapes, 201, 600000, 400000, 10900000, 1200000, "Three Things", 44)
    for i, label in enumerate(("First item", "Second item", "Third item")):
        def kids(sh, label=label, i=i):
            rect(sh, 211 + 10 * i, 0, 0, 800000, 600000, (255, 255, 255))
            tb(sh, 212 + 10 * i, 0, 0, 800000, 600000, label, 24)
        group(s2.shapes, 210 + 10 * i, (600000 + 3800000 * i, 2200000), (3200000, 2400000), (800000, 600000), kids)
    pic(s2.shapes, 241, 200000, 6 * M, M, 600000, (200, 60, 60))

    s3 = blank_slide(prs, (235, 250, 230))
    tb(s3.shapes, 301, 600000, 400000, 10900000, 1200000, "Process", 44)
    for i, label in enumerate(("Plan", "Do", "Check")):
        tb(s3.shapes, 311 + i, M, 2 * M + 1400000 * i, 10 * M, 1200000, label, 20, fill=(255, 255, 255))
    pic(s3.shapes, 321, 11 * M, 6 * M, 800000, 600000, (60, 160, 90))

    s4 = blank_slide(prs, (250, 230, 240))
    tb(s4.shapes, 401, 600000, 400000, 10900000, 1200000, "Compare", 44)
    tb(s4.shapes, 411, 600000, 2 * M, 5200000, 3600000, "Before", 24)
    tb(s4.shapes, 412, 6400000, 2 * M, 5200000, 3600000, "After", 24)
    pic(s4.shapes, 421, 5700000, 6 * M, 800000, 600000, (160, 60, 160))
    # C32 (QA round 1 Q1): a filled label chip and a filled 6% box go when cleared; a filled 10% panel stays, empty
    tb(s4.shapes, 431, 11600000, 500000, 400000, 400000, "07", 18, fill=(240, 170, 60))
    tb(s4.shapes, 441, 600000, 5700000, 4600000, 1100000, "Small note here", 16, fill=(255, 255, 255))
    tb(s4.shapes, 451, 6400000, 5200000, 5400000, 1600000, "Panel text here", 18, fill=(255, 255, 255))

    s5 = blank_slide(prs, (30, 40, 70))
    tb(s5.shapes, 501, M, 2 * M, 10 * M, 2 * M, "Chapter", 60)
    tb(s5.shapes, 511, M, 4500000, 2 * M, 400000, "Part two", 14)
    pic(s5.shapes, 521, 9 * M, 5 * M, 2 * M, M, (220, 200, 60))

    s6 = blank_slide(prs, (245, 245, 245))
    tb(s6.shapes, 601, 600000, 400000, 10900000, 1200000, "Payment rules", 44)
    tb(s6.shapes, 611, 600000, 1800000, 10900000, 4200000, "Use the company credit card for travel.", 20)
    pic(s6.shapes, 621, 10 * M, 6 * M, M, 600000, (90, 90, 90))

    s7 = blank_slide(prs, (255, 255, 255))
    tb(s7.shapes, 701, 600000, 400000, 10900000, 1200000, "Fonts used", 44)
    for i, hexcode in enumerate(("#1A2B3C", "#FFAA00", "#00CC88")):
        tb(s7.shapes, 711 + i, 600000 + 2 * M * i, 3 * M, 1800000, 500000, hexcode, 14)
    pic(s7.shapes, 721, 9 * M, 5 * M, 2 * M, M, (10, 200, 200))

    s8 = blank_slide(prs, (20, 20, 20))
    tb(s8.shapes, 801, M, 2 * M, 10 * M, 2 * M, "Thank you", 60)
    tb(s8.shapes, 811, M, 4500000, 10 * M, 600000, "Questions welcome", 20)
    return save(prs, out, "sample-design.pptx")


def footer_sp(layout, t, text, field, sid):
    """A slide footer placeholder the way PowerPoint writes one: the layout's placeholder with an empty spPr."""
    src = None
    for sp in layout.placeholders:
        if sp.placeholder_format.type is not None and {16: "dt", 15: "ftr", 13: "sldNum"}.get(int(sp.placeholder_format.type)) == t:
            src = sp._element
    sp = copy.deepcopy(src)
    sp.find(q("p:nvSpPr")).find(q("p:cNvPr")).set("id", str(sid))
    pr = sp.find(q("p:spPr"))
    for c in list(pr):
        pr.remove(c)
    tx = sp.find(q("p:txBody"))
    for p in tx.findall(q("a:p")):
        tx.remove(p)
    p = etree.SubElement(tx, q("a:p"))
    if field:
        fld = etree.SubElement(p, q("a:fld"), id="{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}", type=field)
        etree.SubElement(fld, q("a:rPr"), lang="en-US")
        etree.SubElement(fld, q("a:t")).text = text or "‹#›"
    else:
        r = etree.SubElement(p, q("a:r"))
        etree.SubElement(r, q("a:rPr"), lang="en-US")
        etree.SubElement(r, q("a:t")).text = text
    return sp


def make_sample_footer(out):
    """Sample slides on one layout (Title Only): f1 carries ftr and sldNum, f2 carries none, f3 a fixed date, f4 a
    footer inside a group. Each has its own background, a title placeholder and a free body box."""
    prs = new_prs()
    lay = layout_named(prs, "Title Only")
    for k, rgb in enumerate(((240, 230, 220), (220, 240, 230), (230, 220, 240), (240, 240, 210)), start=1):
        s = prs.slides.add_slide(lay)
        bg(s, rgb)
        s.shapes.title.text = f"Footer sample {k}"
        set_id(s.shapes.title, k * 100 + 1)
        tb(s.shapes, k * 100 + 11, 600000, 1800000, 10900000, 3600000, f"Body text {k}", 20)
        tree = s.shapes._spTree
        if k == 1:
            tree.append(footer_sp(lay, "ftr", "Company Confidential", None, 191))
            tree.append(footer_sp(lay, "sldNum", "1", "slidenum", 192))
        if k == 3:
            tree.append(footer_sp(lay, "dt", "2026 年 10 月", None, 391))
        if k == 4:
            def kids(sh):
                rect(sh, 492, 0, 0, 400000, 100000, (200, 200, 200))
            g = group(s.shapes, 490, (600000, 6300000), (4 * M, M), (400000, 100000), kids)
            f = footer_sp(lay, "ftr", "Grouped footer", None, 491)
            xf = etree.SubElement(f.find(q("p:spPr")), q("a:xfrm"))
            etree.SubElement(xf, q("a:off"), x="0", y="0")
            etree.SubElement(xf, q("a:ext"), cx="400000", cy="100000")
            g._element.append(f)
    return save(prs, out, "sample-footer.pptx")


def make_sample_footer_nopos(out):
    """C29's other half: a grouped footer on a layout with no footer placeholder of that type: nothing to place it."""
    prs = new_prs()
    lay = layout_named(prs, "Title Only")
    ftr_lay = next(sp for sp in lay.placeholders if int(sp.placeholder_format.type) == 15)
    s = prs.slides.add_slide(lay)
    bg(s, (230, 230, 250))
    s.shapes.title.text = "No footer place"
    set_id(s.shapes.title, 101)
    tb(s.shapes, 111, 600000, 1800000, 10900000, 3600000, "Body text", 20)

    def kids(sh):
        rect(sh, 192, 0, 0, 400000, 100000, (200, 200, 200))
    g = group(s.shapes, 190, (600000, 6300000), (4 * M, M), (400000, 100000), kids)
    f = footer_sp(lay, "ftr", "Grouped footer", None, 191)
    xf = etree.SubElement(f.find(q("p:spPr")), q("a:xfrm"))
    etree.SubElement(xf, q("a:off"), x="0", y="0")
    etree.SubElement(xf, q("a:ext"), cx="400000", cy="100000")
    g._element.append(f)
    ftr_lay._element.getparent().remove(ftr_lay._element)
    return save(prs, out, "sample-footer-nopos.pptx")


def content_slide(prs, k, rgb, title, body, title_pt=44, body_pt=20):
    s = blank_slide(prs, rgb)
    tb(s.shapes, k * 100 + 1, 600000, 400000, 10900000, 1200000, title, title_pt)
    tb(s.shapes, k * 100 + 11, 600000, 1800000, 10900000, 4200000, body, body_pt)
    return s


def make_sample_chart(out):
    """c2 holds a chart (a graphic frame): never usable, never copied."""
    prs = new_prs()
    content_slide(prs, 1, (240, 230, 220), "Opening", "Opening text")
    s2 = content_slide(prs, 2, (220, 240, 230), "Results chart", "Chart notes")
    data = CategoryChartData()
    data.categories = ["Q1", "Q2"]
    data.add_series("Sales", (1, 2))
    ch = s2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Emu(6 * M), Emu(3 * M), Emu(4 * M), Emu(3 * M), data)
    set_id(ch, 221)
    content_slide(prs, 3, (230, 220, 240), "Details", "Detail text")
    return save(prs, out, "sample-chart.pptx")


def make_sample_jump(out):
    """j1 carries a decorated shape that jumps to j2: on a copy the link and its relationship are gone."""
    prs = new_prs()
    s1 = content_slide(prs, 1, (240, 230, 220), "Agenda", "Agenda text")
    s2 = content_slide(prs, 2, (220, 240, 230), "Details", "Detail text")
    r = rect(s1.shapes, 121, 9 * M, 6 * M, 2 * M, 500000, (60, 60, 200))
    rid = s1.part.relate_to(s2.part, RT.SLIDE)
    c = r._element.find(".//" + q("p:cNvPr"))
    h = etree.SubElement(c, q("a:hlinkClick"))
    h.set(q("r:id"), rid)
    h.set("action", "ppaction://hlinksldjump")
    return save(prs, out, "sample-jump.pptx")


def make_sample_field(out):
    """d1's only body box is a date field: the written run keeps the field's run properties, the field goes."""
    prs = new_prs()
    s = blank_slide(prs, (240, 230, 220))
    tb(s.shapes, 101, 600000, 400000, 10900000, 1200000, "Field sample", 44)
    box = tb(s.shapes, 111, 600000, 1800000, 10900000, 4200000, "x", 20)
    p = box.text_frame.paragraphs[0]._p
    for r in p.findall(q("a:r")):
        p.remove(r)
    fld = etree.SubElement(p, q("a:fld"), id="{11111111-2222-4333-8444-555555555555}", type="datetime1")
    etree.SubElement(fld, q("a:rPr"), lang="en-US", sz="2400", b="1")
    etree.SubElement(fld, q("a:t")).text = "1/11/2026"
    end = p.find(q("a:endParaRPr"))
    if end is not None:
        p.remove(end)
        p.append(end)
    return save(prs, out, "sample-field.pptx")


def make_sample_connector(out):
    """k1: a connector bound to two boxes; the box that gets no text is removed, so its reference goes."""
    prs = new_prs()
    s = blank_slide(prs, (240, 230, 220))
    tb(s.shapes, 101, 600000, 400000, 10900000, 1200000, "Flow", 44)
    a = tb(s.shapes, 111, 600000, 2 * M, 6 * M, 3 * M, "Start here", 20)
    b = tb(s.shapes, 112, 8 * M, 2 * M, 3 * M, M, "End", 20)
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(6600000), Emu(3 * M), Emu(8 * M), Emu(2500000))
    set_id(c, 121)
    c.begin_connect(a, 3)
    c.end_connect(b, 1)
    return save(prs, out, "sample-connector.pptx")


def make_sample_rotated(out):
    """r1's body box sits in a rotated group: a destination the estimate cannot model (check this slide)."""
    prs = new_prs()
    s = blank_slide(prs, (240, 230, 220))
    tb(s.shapes, 101, 600000, 400000, 10900000, 1200000, "Rotated", 44)

    def kids(sh):
        tb(sh, 112, 0, 0, 2 * M, M, "Turned text", 20)
    group(s.shapes, 110, (2 * M, 2 * M), (6 * M, 3 * M), (2 * M, M), kids, rot=900000)
    return save(prs, out, "sample-rotated.pptx")


def make_sample_hidden(out):
    """h1 is a hidden slide; h2 holds a hidden title-size box that is never the title and is scrubbed on the copy."""
    prs = new_prs()
    s1 = content_slide(prs, 1, (240, 230, 220), "Hidden slide", "Hidden body")
    s1._element.set("show", "0")
    s2 = content_slide(prs, 2, (220, 240, 230), "Visible title", "Visible body")
    tb(s2.shapes, 221, 600000, 6 * M, 10 * M, 700000, "SECRET DRAFT", 60, hidden=True)
    return save(prs, out, "sample-hidden.pptx")


def make_sample_equal(out):
    """e1: title and body in one size; e2: two comparison headings in the title's size, far apart."""
    prs = new_prs()
    s1 = blank_slide(prs, (240, 230, 220))
    tb(s1.shapes, 101, 600000, 400000, 10900000, 900000, "Quarterly results", 32)
    tb(s1.shapes, 111, 600000, 1500000, 10900000, 4 * M, "Revenue grew in every region this year", 32)
    s2 = blank_slide(prs, (220, 240, 230))
    tb(s2.shapes, 201, 600000, 400000, 10900000, 900000, "Options", 36)
    tb(s2.shapes, 211, 600000, 2 * M, 4 * M, 3 * M, "Plan A", 36)
    tb(s2.shapes, 212, 7 * M, 2 * M, 4 * M, 3 * M, "Plan B", 36)
    return save(prs, out, "sample-equal.pptx")


def make_sample_closing5(out):
    """Marco's slide 8 arrangement (Thank, you, for, viewing in four boxes plus a line under them) is a closing slide;
    a plain content sample keeps the route available."""
    prs = new_prs()
    content_slide(prs, 1, (240, 230, 220), "Overview", "Overview text")
    s2 = blank_slide(prs, (30, 30, 30))
    for i, (word, x, w) in enumerate((("Thank", 896150, 2353200), ("you", 3641300, 1500300), ("for", 5533375, 1359900), ("viewing", 7285042, 2705400))):
        tb(s2.shapes, 201 + i, x, 3731599, w, 1417200, word, 48)
    tb(s2.shapes, 211, 384709, 5541617, 10116900, 738900, "(and sharing in my misery)!", 48)
    return save(prs, out, "sample-closing5.pptx")


def make_sample_short(out):
    """q1: 3 slots holding Cost, Time, Risk (short words, body boxes) and a 3-box row of big numbers (labels)."""
    prs = new_prs()
    s = blank_slide(prs, (240, 230, 220))
    tb(s.shapes, 101, 600000, 300000, 10900000, 1300000, "Our numbers", 72)
    for i, (num, word) in enumerate((("$1,300", "Cost"), ("4", "Time"), ("11", "Risk"))):
        x = 600000 + 3800000 * i
        tb(s.shapes, 111 + i, x, 1900000, 3200000, 1500000, num, 60, fill=(255, 255, 255))
        tb(s.shapes, 121 + i, x, 3700000, 3200000, 2 * M, word, 24)
    return save(prs, out, "sample-short.pptx")


def make_sample_only(out):
    """No usable layout (only Title Only and Blank remain), 4 decorated sample slides: fills on the sample route."""
    prs = new_prs()
    for name in ("Title Slide", "Title and Content", "Section Header", "Two Content", "Comparison", "Content with Caption",
                 "Picture with Caption", "Title and Vertical Text", "Vertical Title and Text"):
        lay = layout_named(prs, name)
        lay.slide_master.slide_layouts.remove(lay)
    for k, rgb in enumerate(((240, 230, 220), (220, 240, 230), (230, 220, 240), (240, 240, 210)), start=1):
        s = content_slide(prs, k, rgb, f"Only sample {k}", f"Only text {k}")
        pic(s.shapes, k * 100 + 21, 9 * M, 6 * M, M, 600000, (20 * k, 100, 160))
    return save(prs, out, "sample-only.pptx")


def make_sample_thin(out):
    """One usable sample slide, decorated: the only design, so the sample route is the default."""
    prs = new_prs()
    s = content_slide(prs, 1, (30, 60, 90), "Thin sample", "Thin text")
    pic(s.shapes, 121, 9 * M, 5 * M, 2 * M, M, (200, 120, 40))
    return save(prs, out, "sample-thin.pptx")


def make_sample_typo(out):
    """Sample slides on the layout's plain background with all type in free text boxes: typography-only design."""
    prs = new_prs()
    for k in range(1, 4):
        s = prs.slides.add_slide(layout_named(prs, "Blank"))
        tb(s.shapes, k * 100 + 1, 600000, 400000, 10900000, 1200000, f"Typo title {k}", 54)
        tb(s.shapes, k * 100 + 11, 600000, 1800000, 10900000, 4200000, f"Typo body {k}", 22)
    return save(prs, out, "sample-typo.pptx")


def _master_bar(prs):
    """A header bar and a logo drawn on the master (over 5% of the slide): designed layouts."""
    master = prs.slide_masters[0]
    scratch = prs.slides.add_slide(layout_named(prs, "Blank"))
    bar = rect(scratch.shapes, 9001, 0, 0, SW, 900000, (11, 42, 74))
    logo = pic(scratch.shapes, 9002, SW - 1400000, 150000, 1100000, 600000, (242, 140, 40))
    for el in (bar._element, logo._element):
        master.shapes._spTree.append(el)
    rid_old = logo._element.find(".//" + q("a:blip")).get(q("r:embed"))
    img = scratch.part.related_part(rid_old)
    rid = master.part.relate_to(img, RT.IMAGE)
    logo._element.find(".//" + q("a:blip")).set(q("r:embed"), rid)
    sid = prs.slides._sldIdLst[-1]
    prs.part.drop_rel(sid.rId)
    prs.slides._sldIdLst.remove(sid)


def make_layout_design(out):
    """Designed layouts (header bar and logo on the master), plain sample slides on the layout placeholders."""
    prs = new_prs()
    _master_bar(prs)
    for k in range(1, 4):
        s = prs.slides.add_slide(layout_named(prs, "Title and Content"))
        s.shapes.title.text = f"Plain sample {k}"
        s.placeholders[1].text = f"Plain body {k}"
    return save(prs, out, "layout-design.pptx")


def make_layout_photos(out):
    """Header bar and logo on the layouts, sample slides on the layout placeholders, each with one ordinary photo
    over 15% of the slide: the layout route stays the default."""
    prs = new_prs()
    _master_bar(prs)
    for k in range(1, 4):
        s = prs.slides.add_slide(layout_named(prs, "Title and Content"))
        s.shapes.title.text = f"Photo sample {k}"
        s.placeholders[1].text = f"Photo body {k}"
        pic(s.shapes, k * 100 + 21, 5 * M, 2 * M, 6 * M, 4 * M, (40 * k, 120, 160))
    return save(prs, out, "layout-photos.pptx")


def make_sample_titleonly(out):
    """Every sample holds only a title: no sample is compatible with a content slide, so no sample route."""
    prs = new_prs()
    for k in range(1, 3):
        s = blank_slide(prs, (40 * k, 60, 90))
        tb(s.shapes, k * 100 + 1, M, 2 * M, 10 * M, 2 * M, f"Title only {k}", 54)
    return save(prs, out, "sample-titleonly.pptx")


def make_sample_heavy(out):
    """C12/C30 stress case: one sample slide carrying 1,500 small shapes, so 14 copies pass the 20,000 copied-shape cap."""
    prs = new_prs()
    s = content_slide(prs, 1, (240, 230, 220), "Heavy sample", "Heavy text")
    tree = s.shapes._spTree
    proto = rect(s.shapes, 1000, 0, 0, 100000, 100000, (120, 120, 120))._element
    for i in range(1, 1500):
        el = copy.deepcopy(proto)
        el.find(".//" + q("p:cNvPr")).set("id", str(1000 + i))
        off = el.find(".//" + q("a:off"))
        off.set("x", str((i % 100) * 120000))
        off.set("y", str(5 * M + (i // 100) * 110000))
        tree.append(el)
    return save(prs, out, "sample-heavy.pptx")


def _donor_bulk(n_bytes: int):
    """An a:extLst of opaque size n_bytes, legal inside a:rPr and a:pPr."""
    ext = etree.Element(q("a:extLst"))
    e = etree.SubElement(ext, q("a:ext"), uri="{C0FFEE00-0000-4000-8000-000000000001}")
    etree.SubElement(e, "{urn:deckfill:test}pad").text = "x" * n_bytes
    return ext


def make_sample_bigrpr(out):
    """C30: a small source whose donor a:rPr is large (20 KB)."""
    prs = new_prs()
    s = content_slide(prs, 1, (240, 230, 220), "Big run properties", "Body")
    rpr = s.shapes[1].text_frame.paragraphs[0].runs[0]._r.find(q("a:rPr"))
    rpr.append(_donor_bulk(20000))
    return save(prs, out, "sample-bigrpr.pptx")


def make_sample_biglvl2(out):
    """C30: a small source with a small donor whose box defines large level-2 paragraph properties (20 KB)."""
    prs = new_prs()
    s = content_slide(prs, 1, (240, 230, 220), "Big level two", "Body")
    tx = s.shapes[1].text_frame._txBody
    ls = tx.find(q("a:lstStyle"))
    lvl2 = etree.SubElement(ls, q("a:lvl2pPr"), marL="457200")
    lvl2.append(_donor_bulk(20000))
    return save(prs, out, "sample-biglvl2.pptx")


def make_sample_fit(out):
    """C25 fit cases: s1 a title sample with a small title box and a small subtitle box; s2 a content slide whose body
    holds about three lines; s3 three small slots; s4 a content slide with a narrow title box."""
    prs = new_prs()
    s1 = blank_slide(prs, (240, 230, 220))
    tb(s1.shapes, 101, M, 2 * M, 4 * M, 800000, "Fit title", 40)
    tb(s1.shapes, 111, M, 3 * M, 4 * M, 500000, "Fit subtitle", 20)
    s2 = blank_slide(prs, (220, 240, 230))
    tb(s2.shapes, 201, 600000, 400000, 10 * M, 800000, "Fit content", 40)
    tb(s2.shapes, 211, 600000, 1500000, 10 * M, 1200000, "Fit body", 20)
    s3 = blank_slide(prs, (230, 220, 240))
    tb(s3.shapes, 301, 600000, 400000, 10 * M, 800000, "Fit slots", 40)
    for i in range(3):
        tb(s3.shapes, 311 + i, 600000 + 3800000 * i, 2 * M, 3 * M, 600000, f"Slot {i + 1}", 20)
    s4 = blank_slide(prs, (240, 240, 210))
    tb(s4.shapes, 401, 600000, 400000, 2 * M, 800000, "Narrow", 40)
    tb(s4.shapes, 411, 600000, 1500000, 10 * M, 4 * M, "Wide body", 20)
    return save(prs, out, "sample-fit.pptx")


def make_sample_backings(out):
    """C32 on Marco's slide 6 structure: a title, four number labels each over its own separate text-free white
    backing (top level, drawn first), four caption body boxes of different widths. b11 sits on a 9% backing (stays);
    caption 141, the largest body box, sits on a light backing that must stay when it receives text."""
    prs = new_prs()
    s = blank_slide(prs, (30, 60, 90))
    tb(s.shapes, 101, 600000, 300000, 10900000, 1000000, "Health in numbers", 48)
    spots = ((600000, 1500000, 3200000, 1300000), (6400000, 1500000, 2200000, 1300000),
             (600000, 4000000, 2200000, 1300000), (6400000, 4000000, 4800000, 1600000))
    for i, (num, (x, y, w, h)) in enumerate(zip(("$1,300", "4", "2", "11"), spots)):
        rect(s.shapes, 111 + i, x, y, w, h, (255, 255, 255))
        tb(s.shapes, 121 + i, x, y, w, h, num, 40)
    rect(s.shapes, 131, 600000, 2900000, 5200000, 900000, (230, 240, 250))
    caps = ((600000, 2900000, 5200000, 900000), (6400000, 2900000, 3000000, 700000),
            (600000, 5400000, 3400000, 700000), (6400000, 5700000, 2600000, 700000))
    for i, (word, (x, y, w, h)) in enumerate(zip(("Total medical bills", "Times I caught the flu", "Trips to the ER",
                                                 "Sick days used"), caps)):
        tb(s.shapes, 141 + i, x, y, w, h, word, 20)
    return save(prs, out, "sample-backings.pptx")


def make_sample_readable(out):
    """C33 (QA round 1 Q2 to Q4, precedence): r1, the title sample, has a 14 pt title; r2 a 60 pt title over an 8 pt
    body that fits; r3 a 60 pt title over an 18 pt body; r4 a 40 pt title, three 14 pt slots, one of them too short to
    hold its bullet above the bar at the floor, and a 9 pt notes box."""
    prs = new_prs()
    r1 = blank_slide(prs, (240, 230, 220))
    tb(r1.shapes, 101, M, 2 * M, 6 * M, 600000, "Cover", 14)
    pic(r1.shapes, 121, 8 * M, M, 3 * M, 4 * M, (40, 90, 160))
    content_slide(prs, 2, (220, 240, 230), "Sample two", "Small print", 60, 8)
    content_slide(prs, 3, (230, 220, 240), "Sample three", "Readable body", 60, 18)
    r4 = blank_slide(prs, (240, 240, 210))
    tb(r4.shapes, 401, 600000, 300000, 10900000, 1000000, "Sample four", 40)
    for i, h in enumerate((700000, 700000, 230000)):
        tb(r4.shapes, 411 + i, 600000 + 3800000 * i, 1600000, 3200000, h, f"Slot {i + 1}", 14)
    tb(r4.shapes, 421, 600000, 2600000, 10900000, 3800000, "Notes", 9)
    return save(prs, out, "sample-readable.pptx")


def make_sample_small(out):
    """C33: every sample's title is under the 4% bar (14 pt on a 7.5 in slide) and every body under the 2% bar."""
    prs = new_prs()
    content_slide(prs, 1, (240, 230, 220), "Tiny one", "Tiny body", 14, 9)
    content_slide(prs, 2, (220, 240, 230), "Tiny two", "Tiny body", 14, 9)
    return save(prs, out, "sample-small.pptx")


def make_sample_split(out):
    """C33 (Q4): two content samples whose body must split for six bullets, five short and one long. p1 (first in file
    order) is wide and holds 1.9 lines at the floor: one bullet a slide, six slides. p2 is narrow, so the long bullet
    takes two lines, and holds 2.2 lines: four slides. p1's unsplit text runs less far over its floor (3.16 times
    against 3.18), so the rev 8 ratio picked p1; Q4's fewest continuation slides picks p2."""
    prs = new_prs()
    content_slide(prs, 1, (240, 230, 220), "Split one", "Body", 40, 20)
    content_slide(prs, 2, (220, 240, 230), "Split two", "Body", 40, 20)
    prs.slides[0].shapes[1].height = Emu(497000)
    prs.slides[1].shapes[1].width = Emu(4 * M)
    prs.slides[1].shapes[1].height = Emu(561000)
    return save(prs, out, "sample-split.pptx")


# --- QA round 2 fixtures (C34 to C37). Cells of the R3 grid are 190500 EMU square on this 12192000 x 6858000 slide.
C = 190500


def cells(c0, r0, c1, r1):
    """A box covering grid columns c0..c1 and rows r0..r1 exactly."""
    return c0 * C, r0 * C, (c1 - c0 + 1) * C, (r1 - r0 + 1) * C


def _geom(shape, xml_geom):
    pr = shape._element.find(q("p:spPr"))
    old = pr.find(q("a:prstGeom"))
    new = etree.fromstring(xml_geom)
    old.addprevious(new)
    pr.remove(old)


CUSTRECT = ('<a:custGeom xmlns:a="%s"><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/>'
            '<a:pathLst><a:path w="%d" h="%d"><a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="%d" y="0"/></a:lnTo>'
            '<a:lnTo><a:pt x="%d" y="%d"/></a:lnTo><a:lnTo><a:pt x="0" y="%d"/></a:lnTo><a:lnTo><a:pt x="0" y="0"/></a:lnTo>'
            '<a:close/></a:path></a:pathLst></a:custGeom>')
LEAF = ('<a:custGeom xmlns:a="%s"><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/>'
        '<a:pathLst><a:path w="1000" h="1000"><a:moveTo><a:pt x="0" y="500"/></a:moveTo>'
        '<a:cubicBezTo><a:pt x="300" y="0"/><a:pt x="700" y="0"/><a:pt x="1000" y="500"/></a:cubicBezTo>'
        '<a:cubicBezTo><a:pt x="700" y="1000"/><a:pt x="300" y="1000"/><a:pt x="0" y="500"/></a:cubicBezTo>'
        '<a:close/></a:path></a:pathLst></a:custGeom>')


def custrect(shapes, sid, x, y, w, h, rgb):
    """A rectangle written as a four-corner custGeom path with a solid fill, the way Canva exports one (Marco's slide 6
    backings)."""
    s = rect(shapes, sid, x, y, w, h, rgb)
    _geom(s, CUSTRECT % (NS["a"], w, h, w, w, h, h))
    return s


def leaf(shapes, sid, x, y, w, h, rgb):
    s = rect(shapes, sid, x, y, w, h, rgb)
    _geom(s, LEAF % NS["a"])
    return s


def picture_rect(slide, sid, x, y, w, h, rot):
    """A rectangle path filled with a picture and rotated (Marco's olive leaf, shape 74)."""
    p = pic(slide.shapes, 9000 + sid, x, y, w, h, (110, 140, 60))
    rid = p._element.find(".//" + q("a:blip")).get(q("r:embed"))
    s = custrect(slide.shapes, sid, x, y, w, h, (0, 0, 0))
    pr = s._element.find(q("p:spPr"))
    pr.remove(pr.find(q("a:solidFill")))
    bf = etree.SubElement(pr, q("a:blipFill"))
    etree.SubElement(bf, q("a:blip")).set(q("r:embed"), rid)
    etree.SubElement(etree.SubElement(bf, q("a:stretch")), q("a:fillRect"))
    ln = pr.find(q("a:ln"))
    if ln is not None:
        ln.addprevious(bf)
    pr.find(q("a:xfrm")).set("rot", str(rot))
    p._element.getparent().remove(p._element)
    return s


LONG = ("Quarter one: pilot the scheduling tool", "Quarter two: roll it out to every truck",
        "Quarter three: open the cross-border routes", "Quarter four: review and plan next year")


def make_sample_grow(out):
    """C34 grown box. g1: Marco's slide 6 after clearing (a title, four number labels on their own rectangle-path
    backings, four caption body boxes of different widths, a photo on the right). g2: a 70% declared background panel
    behind a small body. g3: a small body boxed in by pictures (no free area of 25% by 15%). g4: a plus-shaped free
    area whose vertical and horizontal bars hold the same area (the top-most wins). g5: Marco's grouped body (a 3.97x
    scaled group holding a white rectangle-path backing, the body box and a side accent). g6: a body on a backing with
    positive margins beside an obstacle. g7: a body under two qualifying backings (no growth)."""
    prs = new_prs()
    g1 = blank_slide(prs, (225, 240, 230))
    tb(g1.shapes, 101, 600000, 300000, 6600000, 900000, "My health in numbers", 40)
    spots = ((600000, 1400000, 2800000, 1100000), (3600000, 1400000, 2400000, 1100000),
             (600000, 3600000, 2600000, 1100000), (3600000, 3600000, 2200000, 1100000))
    for i, (num, (x, y, w, h)) in enumerate(zip(("$1,300", "4", "2", "11"), spots)):
        custrect(g1.shapes, 111 + i, x, y, w, h, (255, 255, 255))
        tb(g1.shapes, 121 + i, x, y, w, h, num, 32)
    caps = ((600000, 2600000, 2800000, 600000), (3600000, 2600000, 2400000, 600000),
            (600000, 4800000, 2600000, 600000), (3600000, 4800000, 2200000, 600000))
    for i, (word, (x, y, w, h)) in enumerate(zip(("Total medical bills", "Times I caught the flu", "Trips to the ER",
                                                 "Sick days used"), caps)):
        tb(g1.shapes, 131 + i, x, y, w, h, word, 18)
    pic(g1.shapes, 141, 7400000, 300000, 4400000, 6200000, (90, 90, 90))

    g2 = blank_slide(prs, (240, 230, 220))
    rect(g2.shapes, 201, 800000, 700000, 10600000, 5500000, (250, 250, 250))
    tb(g2.shapes, 211, 1000000, 800000, 8 * M, 800000, "Behind the panel", 36)
    tb(g2.shapes, 221, 1000000, 2 * M, 3 * M, 500000, "Body", 18)

    g3 = blank_slide(prs, (230, 220, 240))
    tb(g3.shapes, 301, 600000, 300000, 10 * M, 800000, "Boxed in", 36)
    tb(g3.shapes, 311, 4800000, 3 * M, 2400000, 500000, "Body", 18)
    for i, (x, y, w, h) in enumerate(((600000, 1300000, 4100000, 5 * M), (7300000, 1300000, 4300000, 5 * M),
                                      (4800000, 1300000, 2400000, 1600000), (4800000, 3600000, 2400000, 2700000))):
        pic(g3.shapes, 321 + i, x, y, w, h, (60 + 30 * i, 90, 120))

    g4 = blank_slide(prs, (240, 240, 210))
    blocks = ((3, 2, 23, 13), (40, 2, 60, 13), (3, 20, 23, 33), (40, 20, 60, 33), (24, 2, 39, 7), (24, 26, 39, 33),
              (3, 14, 7, 19), (56, 14, 60, 19))
    for i, b in enumerate(blocks):
        pic(g4.shapes, 401 + i, *cells(*b), (80, 100 + 10 * i, 140))
    tb(g4.shapes, 411, *cells(5, 4, 18, 8), "Plus", 36)
    tb(g4.shapes, 421, *cells(30, 16, 33, 17), "Body", 18)

    g5 = blank_slide(prs, (230, 240, 250))
    tb(g5.shapes, 501, 600000, 300000, 10 * M, 800000, "Grouped body", 36)

    def kids(sh):
        custrect(sh, 511, 0, 57114, 1123000, 246486, (255, 255, 255))
        tb(sh, 512, 0, 0, 1123000, 303600, "Body", 18)
        rect(sh, 513, 1173000, 60000, 60000, 180000, (240, 120, 60))
    group(g5.shapes, 510, (600000, 2 * M), (4902000, 1206562), (1233000, 303600), kids)

    g6 = blank_slide(prs, (245, 235, 225))
    tb(g6.shapes, 601, 600000, 300000, 10 * M, 800000, "Margins", 36)
    custrect(g6.shapes, 611, 600000, 2 * M, 3400000, 900000, (255, 255, 255))
    tb(g6.shapes, 612, 800000, 2200000, 3 * M, 500000, "Body", 18)
    pic(g6.shapes, 621, 7 * M, 1500000, 600000, 4 * M, (120, 60, 60))

    g7 = blank_slide(prs, (235, 245, 225))
    tb(g7.shapes, 701, 600000, 300000, 10 * M, 800000, "Two backings", 36)
    custrect(g7.shapes, 711, 700000, 1900000, 3200000, 700000, (255, 255, 255))
    custrect(g7.shapes, 712, 750000, 1950000, 3100000, 600000, (250, 250, 250))
    tb(g7.shapes, 721, 800000, 2 * M, 3 * M, 500000, "Body", 18)
    return save(prs, out, "sample-grow.pptx")


def make_sample_geom(out):
    """C36 backings by geometry: four labels, each over a text-free shape: a curved leaf path (stays), a rect preset
    (goes), a four-corner rectangle path like Marco's slide 6 backings (goes), a rotated picture-filled rectangle path
    like Marco's olive leaf (stays). One caption body takes the outline."""
    prs = new_prs()
    s = blank_slide(prs, (230, 235, 245))
    tb(s.shapes, 101, 600000, 300000, 10 * M, 900000, "Backings by shape", 40)
    xs = (600000, 3400000, 6200000, 9000000)
    leaf(s.shapes, 111, xs[0], 1500000, 2400000, 1200000, (90, 160, 90))
    rect(s.shapes, 112, xs[1], 1500000, 2400000, 1200000, (255, 255, 255))
    custrect(s.shapes, 113, xs[2], 1500000, 2400000, 1200000, (255, 255, 255))
    picture_rect(s, 114, xs[3], 1500000, 2400000, 1200000, 6861076)
    for i, (x, num) in enumerate(zip(xs, ("1", "2", "3", "4"))):
        tb(s.shapes, 121 + i, x, 1500000, 2400000, 1200000, num, 28)
    tb(s.shapes, 131, 600000, 3200000, 10 * M, 2500000, "Caption body", 20)
    return save(prs, out, "sample-geom.pptx")


def make_sample_order(out):
    """C35. o1: a content sample whose body holds six bullets on one slide; o2: one whose body holds three; o3: three
    24 pt slots too small for their bullets (they would be warned); o4: a narrow title box where 時間表 fits and
    時間表（續） does not, over a body that splits."""
    prs = new_prs()
    content_slide(prs, 1, (240, 230, 220), "Order one", "Body", 40, 20)
    content_slide(prs, 2, (220, 240, 230), "Order two", "Body", 40, 20)
    prs.slides[1].shapes[1].height = Emu(1300000)
    s3 = blank_slide(prs, (230, 220, 240))
    tb(s3.shapes, 301, 600000, 400000, 10 * M, 800000, "Order three", 40)
    for i in range(3):
        tb(s3.shapes, 311 + i, 600000 + 3800000 * i, 2 * M, 1500000, 400000, f"Slot {i + 1}", 24)
    s4 = blank_slide(prs, (240, 240, 210))
    tb(s4.shapes, 401, 600000, 400000, 2 * M, 800000, "窄標題", 40)
    tb(s4.shapes, 411, 600000, 1500000, 10 * M, 1000000, "Wide body", 20)
    return save(prs, out, "sample-order.pptx")


def make_sample_two(out):
    """C37: two usable decorated content samples beside python-pptx's layouts: both routes, the layout route default."""
    prs = new_prs()
    for k in (1, 2):
        s = content_slide(prs, k, (240 - 20 * k, 230, 220), f"Two sample {k}", "Body")
        pic(s.shapes, k * 100 + 21, 9 * M, 6 * M, M, 600000, (40 * k, 100, 160))
    return save(prs, out, "sample-two.pptx")


def make_sample_only2(out):
    """C37: no usable layout and two decorated samples: the sample route is the only route, so it is used."""
    prs = new_prs()
    for name in ("Title Slide", "Title and Content", "Section Header", "Two Content", "Comparison", "Content with Caption",
                 "Picture with Caption", "Title and Vertical Text", "Vertical Title and Text"):
        lay = layout_named(prs, name)
        lay.slide_master.slide_layouts.remove(lay)
    for k in (1, 2):
        s = content_slide(prs, k, (240 - 20 * k, 230, 220), f"Only two {k}", "Body")
        pic(s.shapes, k * 100 + 21, 9 * M, 6 * M, M, 600000, (40 * k, 100, 160))
    return save(prs, out, "sample-only2.pptx")


def make_sample_cover(out):
    """C38: c1, the cover, has a title box the deck title needs a small shrink in (still readable) and a 20 pt
    subtitle box; c2, a content sample, fits the title and the subtitle at full size."""
    prs = new_prs()
    c1 = blank_slide(prs, (30, 50, 90))
    tb(c1.shapes, 101, M, 2 * M, 5 * M, 1200000, "Cover title", 40)
    tb(c1.shapes, 111, M, 3300000, 5 * M, 600000, "Cover subtitle", 20)
    pic(c1.shapes, 121, 7 * M, M, 4 * M, 5 * M, (200, 120, 40))
    content_slide(prs, 2, (220, 240, 230), "Content title", "Content body", 40, 20)
    return save(prs, out, "sample-cover.pptx")


def make_sample_cover2(out):
    """C38: the cover's title meets the 4% bar but its subtitle box is 8 pt, under the 2% bar; c2 is readable."""
    prs = new_prs()
    c1 = blank_slide(prs, (30, 50, 90))
    tb(c1.shapes, 101, M, 2 * M, 10 * M, 900000, "Cover title", 40)
    tb(c1.shapes, 111, M, 3 * M, 10 * M, 600000, "Cover subtitle", 8)
    pic(c1.shapes, 121, 9 * M, 4 * M, 2 * M, 2 * M, (200, 120, 40))
    content_slide(prs, 2, (220, 240, 230), "Content title", "Content body", 40, 20)
    return save(prs, out, "sample-cover2.pptx")


def make_sample_cols(out):
    """C38 (S2): k1 a cover; k2 a two-column sample whose boxes hold two bullets each at the floor; k3 a content
    sample whose body holds six."""
    prs = new_prs()
    k1 = blank_slide(prs, (30, 50, 90))
    tb(k1.shapes, 101, M, 2 * M, 10 * M, 1 * M, "Cols cover", 40)
    s2 = blank_slide(prs, (240, 230, 220))
    tb(s2.shapes, 201, 600000, 400000, 10900000, 1000000, "Two columns", 40)
    tb(s2.shapes, 211, 600000, 2 * M, 5 * M, 600000, "Left", 20)
    tb(s2.shapes, 212, 6400000, 2 * M, 5 * M, 600000, "Right", 20)
    content_slide(prs, 3, (220, 240, 230), "One body", "Body", 40, 20)
    return save(prs, out, "sample-cols.pptx")


GUIDERECT = ('<a:custGeom xmlns:a="%s"><a:avLst/><a:gdLst><a:gd name="gd1" fmla="val 0"/></a:gdLst><a:ahLst/>'
             '<a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/><a:pathLst><a:path><a:moveTo><a:pt x="gd1" y="t"/></a:moveTo>'
             '<a:lnTo><a:pt x="w" y="t"/></a:lnTo><a:lnTo><a:pt x="w" y="h"/></a:lnTo><a:lnTo><a:pt x="l" y="h"/></a:lnTo>'
             '<a:close/></a:path></a:pathLst></a:custGeom>')


def make_sample_malformed(out):
    """Code review F2. m1: a decorated content sample. m2: a content sample with a number label over a chip drawn
    as a rectangle path whose corners are guide names (gd1, w, h, l, t), so it is never a backing. m3: a content
    sample whose body box has an unreadable offset (x="bad"): only m3 is unusable, both routes still fill."""
    prs = new_prs()
    s1 = content_slide(prs, 1, (240, 230, 220), "Malformed one", "Body one")
    pic(s1.shapes, 121, 9 * M, 6 * M, M, 600000, (40, 100, 160))
    s2 = content_slide(prs, 2, (220, 240, 230), "Malformed two", "Body two")
    s2.shapes[1].top = Emu(3 * M)
    s2.shapes[1].height = Emu(3 * M)
    chip = rect(s2.shapes, 211, 600000, 1700000, 1 * M, 1 * M, (255, 255, 255))
    _geom(chip, GUIDERECT % NS["a"])
    tb(s2.shapes, 221, 600000, 1700000, 1 * M, 1 * M, "1", 28)
    s3 = content_slide(prs, 3, (230, 220, 240), "Malformed three", "Body three")
    s3.shapes[1]._element.find(q("p:spPr")).find(q("a:xfrm")).find(q("a:off")).set("x", "bad")
    return save(prs, out, "sample-malformed.pptx")


MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
TABLE = ('<p:graphicFrame xmlns:p="%s" xmlns:a="%s"><p:nvGraphicFramePr><p:cNvPr id="%d" name="T%d"/>'
         '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
         '<p:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></p:xfrm><a:graphic>'
         '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblGrid>'
         '<a:gridCol w="%d"/></a:tblGrid><a:tr h="370840"><a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>'
         '<a:rPr lang="en-US"/><a:t>%s</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc></a:tr></a:tbl></a:graphicData>'
         '</a:graphic></p:graphicFrame>')


def alt(el, choice):
    """Wrap a shape in mc:AlternateContent: the given element as the p14 choice, the shape itself as the fallback."""
    ac = etree.Element("{%s}AlternateContent" % MC, nsmap={"mc": MC})
    ch = etree.SubElement(ac, "{%s}Choice" % MC, nsmap={"p14": P14}, Requires="p14")
    fb = etree.SubElement(ac, "{%s}Fallback" % MC)
    el.addprevious(ac)
    ch.append(choice)
    fb.append(el)
    return ac


def _retext(el, text):
    for t in el.iter(q("a:t")):
        t.text = text
    return el


def make_sample_altcontent(out):
    """Code review F1. a1: its body box and a filled note sit in mc:AlternateContent whose p14 choice holds other
    words; a2: a choice holds a table, the fallback a picture. Copies show the fallback only, so no choice words reach
    the deck and the table never does; a3: the fallback holds a table (a choice a picture), so a3 is never usable."""
    prs = new_prs()
    s1 = content_slide(prs, 1, (240, 230, 220), "Alt one", "Fallback body words")
    body = s1.shapes[1]._element
    alt(body, _retext(copy.deepcopy(body), "Choice body words"))
    note = tb(s1.shapes, 131, 9 * M, 6 * M, 2 * M, 400000, "Fallback note", 14, fill=(60, 60, 200))._element
    alt(note, _retext(copy.deepcopy(note), "Choice note"))
    s2 = content_slide(prs, 2, (220, 240, 230), "Alt two", "Body two")
    s2.shapes[1].height = Emu(2 * M)
    picture = pic(s2.shapes, 231, 6 * M, 4500000, 4 * M, 1500000, (40, 100, 160))._element
    alt(picture, etree.fromstring(TABLE % (NS["p"], NS["a"], 231, 231, 6 * M, 4500000, 4 * M, 1500000, 4 * M,
                                           "Choice table cell")))
    s3 = content_slide(prs, 3, (230, 220, 240), "Alt three", "Body three")
    s3.shapes[1].height = Emu(2 * M)
    choice_pic = pic(s3.shapes, 331, 6 * M, 4500000, 4 * M, 1500000, (160, 100, 40))._element
    table = etree.fromstring(TABLE % (NS["p"], NS["a"], 331, 331, 6 * M, 4500000, 4 * M, 1500000, 4 * M, "Fallback cell"))
    choice_pic.addprevious(table)
    alt(table, choice_pic)
    return save(prs, out, "sample-altcontent.pptx")


def _flip(g, h=False, v=False):
    xf = g._element.find(q("p:grpSpPr")).find(q("a:xfrm"))
    if h:
        xf.set("flipH", "1")
    if v:
        xf.set("flipV", "1")


def make_sample_flip(out):
    """Code review F3: an unrotated body outside a flipped group whose off-centre picture, once flipped, sits right
    beside the body. f1: flipH, the picture's child box (6M, 0, 2M, 4M) in an 8M by 4M group at (3.8M, 1.5M) is drawn at
    (3.8M, 1.5M, 2M, 4M), to the body's right. f2: flipV, the child box (0, 2M, 6M, 1M) in a 6M by 3M group at
    (0.6M, 3.4M) is drawn at (0.6M, 3.4M, 6M, 1M), under the body. Unflipped, both would sit far from the body."""
    prs = new_prs()
    f1 = blank_slide(prs, (235, 240, 250))
    tb(f1.shapes, 101, 600000, 300000, 10 * M, 800000, "Flipped across", 36)
    tb(f1.shapes, 111, 600000, 2 * M, 3 * M, 500000, "Body", 18)
    g = group(f1.shapes, 120, (3800000, 1500000), (8 * M, 4 * M), (8 * M, 4 * M),
              lambda sh: pic(sh, 121, 6 * M, 0, 2 * M, 4 * M, (120, 60, 60)))
    _flip(g, h=True)
    f2 = blank_slide(prs, (250, 240, 235))
    tb(f2.shapes, 201, 600000, 300000, 10 * M, 800000, "Flipped down", 36)
    tb(f2.shapes, 211, 600000, 1600000, 3 * M, 500000, "Body", 18)
    g = group(f2.shapes, 220, (600000, 3400000), (6 * M, 3 * M), (6 * M, 3 * M),
              lambda sh: pic(sh, 221, 0, 2 * M, 6 * M, M, (60, 120, 60)))
    _flip(g, v=True)
    return save(prs, out, "sample-flip.pptx")


def make_sample_cols2(out):
    """Code review F4 (S2 with a sample that serves both two and content): k1 a cover; k2 the only body sample, a
    two-column pair whose left box is tall (4.6M) and whose right box holds two bullets at the floor (0.6M)."""
    prs = new_prs()
    k1 = blank_slide(prs, (30, 50, 90))
    tb(k1.shapes, 101, M, 2 * M, 10 * M, 1 * M, "Cols cover", 40)
    s2 = blank_slide(prs, (240, 230, 220))
    tb(s2.shapes, 201, 600000, 400000, 10900000, 1000000, "Two columns", 40)
    tb(s2.shapes, 211, 600000, 1600000, 5 * M, 4600000, "Left", 20)
    tb(s2.shapes, 212, 6400000, 1600000, 5 * M, 600000, "Right", 20)
    return save(prs, out, "sample-cols2.pptx")


def make_sample_inherit(out):
    """Code review F6 (C25 resolved sizes): no written run carries a size of its own. i1: title and body placeholders
    on Title and Content, whose body placeholder sets level 1 to 24 pt at 90% line spacing; level 2 and the spacing
    before come from the master's body style (28 pt, 20%). i2: a free body box with no size anywhere (the
    presentation's default text style, 18 pt). i3: a free body box whose own list style sets level 2 to 14 pt, 6 pt
    before, a 0.6M margin."""
    prs = new_prs()
    lay = layout_named(prs, "Title and Content")
    body_ph = next(sp for sp in lay.placeholders if sp.placeholder_format.idx == 1)
    lst = body_ph._element.find(".//" + q("a:lstStyle"))
    l1 = etree.SubElement(lst, q("a:lvl1pPr"))
    etree.SubElement(etree.SubElement(l1, q("a:lnSpc")), q("a:spcPct"), val="90000")
    etree.SubElement(l1, q("a:defRPr"), sz="2400")
    i1 = prs.slides.add_slide(lay)
    bg(i1, (240, 230, 220))
    i1.shapes.title.text = "Inherited title"
    set_id(i1.shapes.title, 101)
    body = next(sp for sp in i1.placeholders if sp.placeholder_format.idx == 1)
    body.text = "Inherited body"
    set_id(body, 111)
    i2 = blank_slide(prs, (220, 240, 230))
    tb(i2.shapes, 201, 600000, 400000, 10900000, 1000000, "Default style", 40)
    free = i2.shapes.add_textbox(Emu(600000), Emu(1800000), Emu(10900000), Emu(4200000))
    set_id(free, 211)
    free.text_frame.word_wrap = True
    free.text_frame.text = "Default body"
    i3 = blank_slide(prs, (230, 220, 240))
    tb(i3.shapes, 301, 600000, 400000, 10900000, 1000000, "Own level two", 40)
    own = tb(i3.shapes, 311, 600000, 1800000, 10900000, 4200000, "Own body", 20)
    lst = own._element.find(".//" + q("a:lstStyle"))
    l2 = etree.SubElement(lst, q("a:lvl2pPr"), marL="600000")
    etree.SubElement(etree.SubElement(l2, q("a:spcBef")), q("a:spcPts"), val="600")
    etree.SubElement(l2, q("a:defRPr"), sz="1400")
    return save(prs, out, "sample-inherit.pptx")


def make_sample_footbig(out, bad_geometry=False):
    """Code review E1 (C30 borrowed footers): b1, a decorated content sample with no footer of its own; b2, a hidden
    slide on the same layout whose footer holds 1 MB of text. D4 step 1 gives every copy of b1 that footer.
    bad_geometry (round 2, Edge 2): the footer's offset is x="bad", so reading its box fails."""
    prs = new_prs()
    lay = layout_named(prs, "Blank")
    b1 = prs.slides.add_slide(lay)
    bg(b1, (240, 230, 220))
    tb(b1.shapes, 101, 600000, 400000, 10900000, 1200000, "Footer borrower", 44)
    tb(b1.shapes, 111, 600000, 1800000, 10900000, 4200000, "Body", 20)
    pic(b1.shapes, 121, 9 * M, 6 * M, M, 600000, (40, 100, 160))
    b2 = prs.slides.add_slide(lay)
    b2._element.set("show", "0")
    import hashlib  # incompressible text, so the package stays under the D1b compression-ratio cap

    text = "".join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(1024 * 1024 // 64))
    f = footer_sp(lay, "ftr", text, None, 291)
    if bad_geometry:
        xf = etree.SubElement(f.find(q("p:spPr")), q("a:xfrm"))
        etree.SubElement(xf, q("a:off"), x="bad", y="6300000")
        etree.SubElement(xf, q("a:ext"), cx="4000000", cy="300000")
    b2.shapes._spTree.append(f)
    return save(prs, out, "sample-footbad.pptx" if bad_geometry else "sample-footbig.pptx")


def make_sample_badidx(out):
    """Code review round 2, Edge 1: Title and Content has no footer box of its own. x1, hidden, carries a footer
    whose idx is "bad"; x2, a decorated content sample on the same layout, has none. D4 step 1 borrows x1's footer
    for new slides on that layout and must place it itself, which reads its idx."""
    prs = new_prs()
    lay = layout_named(prs, "Title and Content")
    src = footer_sp(layout_named(prs, "Title Only"), "ftr", "Bad index footer", None, 191)
    for sp in list(lay.placeholders):
        if sp.placeholder_format.type is not None and int(sp.placeholder_format.type) == 15:  # ftr
            sp._element.getparent().remove(sp._element)
    for k in (1, 2):
        s = prs.slides.add_slide(lay)
        bg(s, (240, 230 - 10 * k, 220))
        s.shapes.title.text = f"Bad index {k}"
        set_id(s.shapes.title, k * 100 + 1)
        body = next(sp for sp in s.placeholders if sp.placeholder_format.idx == 1)
        body.text = f"Body {k}"
        set_id(body, k * 100 + 11)
        if k == 1:
            s._element.set("show", "0")
            src.find(q("p:nvSpPr")).find(q("p:nvPr")).find(q("p:ph")).set("idx", "bad")
            s.shapes._spTree.append(src)
    return save(prs, out, "sample-badidx.pptx")


def make_sample_flipchip(out):
    """Code review round 2, N1 (Q1 on drawn bounds): a kept body (0.6M, 1.5M, 5M, 3M) and two small filled number
    shapes in a group over the right of the slide. f1: the group (0.6M, 1.5M, 11M by 3M, scale 1) is flipped
    horizontally; chip 121's child box (10M, 1M, 1M, 1M) is drawn at (0.6M, 2.5M), behind the body, so it stays as
    its backing; chip 122's child box (1M, 1M, 1M, 1M) is stored behind the body but drawn at (9.6M, 2.5M), so it goes.
    f2: the same with the group rotated 180 degrees instead; chip 221 (10M, 0.5M) is drawn at (0.6M, 3M), behind the
    body; chip 222 (1M, 1.5M) is drawn at (9.6M, 2M)."""
    prs = new_prs()
    for k, (a, b, how) in enumerate((((10 * M, M), (M, M), "flip"), ((10 * M, 500000), (M, 1500000), "rot")), start=1):
        s = blank_slide(prs, (235 + 5 * k, 240, 250))
        tb(s.shapes, k * 100 + 1, 600000, 300000, 10 * M, 800000, f"Chips {how}", 40)
        tb(s.shapes, k * 100 + 11, 600000, 1500000, 5 * M, 3 * M, "Body", 20)

        def kids(sh, k=k, a=a, b=b):
            tb(sh, k * 100 + 21, a[0], a[1], M, M, "1", 14, fill=(255, 255, 255))
            tb(sh, k * 100 + 22, b[0], b[1], M, M, "2", 14, fill=(255, 255, 255))
        g = group(s.shapes, k * 100 + 20, (600000, 1500000), (11 * M, 3 * M), (11 * M, 3 * M), kids,
                  rot=10800000 if how == "rot" else None)
        if how == "flip":
            _flip(g, h=True)
    return save(prs, out, "sample-flipchip.pptx")


def make_all(out) -> list:
    return [
        make_sample_design(out), make_sample_footer(out), make_sample_footer_nopos(out), make_sample_chart(out),
        make_sample_jump(out), make_sample_field(out), make_sample_connector(out), make_sample_rotated(out),
        make_sample_hidden(out), make_sample_equal(out), make_sample_closing5(out), make_sample_short(out),
        make_sample_only(out), make_sample_thin(out), make_sample_typo(out), make_layout_design(out),
        make_layout_photos(out), make_sample_titleonly(out), make_sample_heavy(out), make_sample_bigrpr(out),
        make_sample_biglvl2(out), make_sample_fit(out), make_sample_backings(out), make_sample_readable(out),
        make_sample_small(out), make_sample_split(out), make_sample_grow(out), make_sample_geom(out),
        make_sample_order(out), make_sample_two(out), make_sample_only2(out), make_sample_cover(out),
        make_sample_cover2(out), make_sample_cols(out), make_sample_malformed(out),
        make_sample_altcontent(out), make_sample_flip(out),
        make_sample_cols2(out), make_sample_inherit(out),
        make_sample_footbig(out), make_sample_flipchip(out), make_sample_footbig(out, bad_geometry=True),
        make_sample_badidx(out),
    ]
