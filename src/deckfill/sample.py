"""The sample-slide route's reading side (rev 8, D11 and D12): which sample slides a template has, which of them
are usable, what each one's title, body boxes, labels and list slots are, and whether the template's design lives
on its sample slides.

Every box is measured in slide space: a shape's a:xfrm composed through each enclosing group's off, ext, chOff and
chExt. Sizes are hundredths of a point, as OOXML writes them; geometry is EMU.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass

from lxml import etree

from .template import (
    DEF_LR_INS,
    DEF_TB_INS,
    EMU_PER_PT,
    FOOTER_TYPES,
    UNMODELLED_VERT,
    Fit,
    Level,
    find_master_ph,
    lvl_ppr,
    ph_idx,
    ph_of,
    ph_type,
    placeholders,
)
from .xmlsafe import R_NS, q

DEF_SIZE = 1800
INSTRUCTION_PHRASES = (
    "this presentation template", "free for everyone", "free for personal", "fonts used", "uses the following",
    "use these in your presentation", "delete or hide", "credits", "photos, graphics",
    "范本使用", "範本使用", "字型", "字體下載", "鳴謝",
)
CLOSING_STARTS = ("thank you", "thanks", "謝謝", "多謝", "q&a", "questions")
_HEX = re.compile(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])")
_LABEL = re.compile(r"^[0-9 .,:/%\-+$]{1,6}$")
_PUNCT = re.compile(r"[^\w\s&]", re.UNICODE)
SHAPE_TAGS = ("p:sp", "p:pic", "p:grpSp", "p:cxnSp", "p:graphicFrame", "p:contentPart")
FILL_TAGS = ("a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill")


# ---------------------------------------------------------------------------------------------
# geometry


@dataclass(frozen=True)
class Xf:
    """A group's child-to-parent mapping: parent = off + (child - chOff) * ext / chExt."""

    ox: float
    oy: float
    sx: float
    sy: float
    cx0: float
    cy0: float

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return self.ox + (x - self.cx0) * self.sx, self.oy + (y - self.cy0) * self.sy


def _xfrm_el(el):
    """The a:xfrm (or p:xfrm on a graphic frame) of a shape or group element."""
    tag = etree.QName(el).localname
    if tag == "grpSp":
        pr = el.find(q("p:grpSpPr"))
        return None if pr is None else pr.find(q("a:xfrm"))
    if tag == "graphicFrame":
        return el.find(q("p:xfrm"))
    pr = el.find(q("p:spPr"))
    return None if pr is None else pr.find(q("a:xfrm"))


def _local_box(el):
    x = _xfrm_el(el)
    if x is None:
        return None
    off, ext = x.find(q("a:off")), x.find(q("a:ext"))
    if off is None or ext is None:
        return None
    return int(off.get("x", 0)), int(off.get("y", 0)), int(ext.get("cx", 0)), int(ext.get("cy", 0))


def _turned(el) -> bool:
    x = _xfrm_el(el)
    if x is None:
        return False
    return int(x.get("rot", "0") or 0) % 21600000 != 0 or x.get("flipH") in ("1", "true") or x.get("flipV") in ("1", "true")


def group_xf(grp) -> Xf | None:
    x = _xfrm_el(grp)
    if x is None:
        return None
    off, ext, choff, chext = (x.find(q("a:" + t)) for t in ("off", "ext", "chOff", "chExt"))
    if off is None or ext is None:
        return None
    ox, oy = int(off.get("x", 0)), int(off.get("y", 0))
    ex, ey = int(ext.get("cx", 0)), int(ext.get("cy", 0))
    c0x = int(choff.get("x", 0)) if choff is not None else ox
    c0y = int(choff.get("y", 0)) if choff is not None else oy
    cex = int(chext.get("cx", 0)) if chext is not None else ex
    cey = int(chext.get("cy", 0)) if chext is not None else ey
    return Xf(ox, oy, ex / cex if cex else 1.0, ey / cey if cey else 1.0, c0x, c0y)


def to_slide(box, chain: tuple[Xf, ...]) -> tuple[int, int, int, int]:
    """A local box composed through its enclosing groups, innermost first."""
    x, y, cx, cy = box
    x1, y1 = float(x), float(y)
    x2, y2 = float(x + cx), float(y + cy)
    for xf in chain:
        x1, y1 = xf.apply(x1, y1)
        x2, y2 = xf.apply(x2, y2)
    return round(min(x1, x2)), round(min(y1, y2)), round(abs(x2 - x1)), round(abs(y2 - y1))


def to_local(box, chain: tuple[Xf, ...]) -> tuple[int, int, int, int]:
    """The inverse of to_slide: a slide-space box written back in a shape's own coordinates (D12)."""
    x, y, cx, cy = box
    x1, y1, x2, y2 = float(x), float(y), float(x + cx), float(y + cy)
    for xf in reversed(chain):
        x1, y1 = xf.cx0 + (x1 - xf.ox) / (xf.sx or 1.0), xf.cy0 + (y1 - xf.oy) / (xf.sy or 1.0)
        x2, y2 = xf.cx0 + (x2 - xf.ox) / (xf.sx or 1.0), xf.cy0 + (y2 - xf.oy) / (xf.sy or 1.0)
    return round(min(x1, x2)), round(min(y1, y2)), round(abs(x2 - x1)), round(abs(y2 - y1))


MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
MC_AC, MC_FB = "{%s}AlternateContent" % MC_NS, "{%s}Fallback" % MC_NS


def normalise_alternates(root) -> int:
    """Code review F1: every mc:AlternateContent under root, nested ones included, is replaced by the children of
    its mc:Fallback (removed when it has none). The reader classifies, the fill edits and PowerPoint draws the same
    tree, so no choice branch can show a sample's words. Returns how many were replaced."""
    n = 0
    while True:
        ac = next(root.iter(MC_AC), None)  # lxml filters by tag in C: one fast pass when there is none
        if ac is None:
            return n
        fb = ac.find(MC_FB)
        for c in list(fb) if fb is not None else []:
            ac.addprevious(c)
        ac.getparent().remove(ac)
        n += 1


@dataclass
class Walked:
    el: object
    chain: tuple[Xf, ...]  # enclosing groups, innermost first
    hidden: bool
    turned: bool  # this shape or an enclosing group is rotated or flipped
    top: bool  # a direct child of the slide's shape tree


def walk(sptree):
    """Every shape element of a shape tree, groups included, with its group chain."""
    out: list[Walked] = []

    def rec(parent, chain, hidden, turned, top):
        for el in parent:
            if not isinstance(el.tag, str):
                continue  # comments, processing instructions
            tag = etree.QName(el).localname
            if tag == "AlternateContent":
                # mc:AlternateContent: read the fallback branch, as a non-Office renderer would
                fb = next((c for c in el if isinstance(c.tag, str) and etree.QName(c).localname == "Fallback"), None)
                if fb is not None:
                    rec(fb, chain, hidden, turned, top)
                continue
            if tag not in ("sp", "pic", "grpSp", "cxnSp", "graphicFrame", "contentPart"):
                continue
            h = hidden or _is_hidden(el)
            t = turned or _turned(el)
            out.append(Walked(el, chain, h, t, top))
            if tag == "grpSp":
                xf = group_xf(el)
                rec(el, ((xf,) if xf else ()) + chain, h, t, False)

    rec(sptree, (), False, False, True)
    return out


def _cnvpr(el):
    for c in el:
        if etree.QName(c).localname.startswith("nv"):
            return c.find(q("p:cNvPr"))
    return None


def _is_hidden(el) -> bool:
    c = _cnvpr(el)
    return c is not None and c.get("hidden") in ("1", "true")


def shape_id(el) -> int | None:
    c = _cnvpr(el)
    if c is None or not (c.get("id") or "").isdigit():
        return None
    return int(c.get("id"))


# ---------------------------------------------------------------------------------------------
# text, sizes and spacing


def text_of(sp) -> str:
    tx = sp.find(q("p:txBody"))
    if tx is None:
        return ""
    paras = []
    for p in tx.findall(q("a:p")):
        paras.append("".join(t.text or "" for t in p.iter(q("a:t"))))
    return "\n".join(paras)


def has_text(sp) -> bool:
    tx = sp.find(q("p:txBody"))
    if tx is None:
        return False
    if any((t.text or "").strip() for t in tx.iter(q("a:t"))):
        return True
    return tx.find(".//" + q("a:fld")) is not None


def donor(sp):
    """D12 donor run: the first run or field of the box's first paragraph that has one. Returns (paragraph, run)."""
    tx = sp.find(q("p:txBody"))
    if tx is None:
        return None, None
    for p in tx.findall(q("a:p")):
        for c in p:
            if c.tag in (q("a:r"), q("a:fld")):
                return p, c
    paras = tx.findall(q("a:p"))
    return (paras[0] if paras else None), None


def _lvl(p) -> int:
    ppr = None if p is None else p.find(q("a:pPr"))
    return int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1


@dataclass(frozen=True)
class LevelSpec:
    """One paragraph level as written: effective size (hundredths of a point), line spacing and spacing before and
    after as ('pct', fraction of single spacing) or ('pts', EMU) or ('', 0), left margin (EMU)."""

    size: int
    ln: tuple[str, float]
    bef: tuple[str, float]
    aft: tuple[str, float]
    margin: int

    def at(self, size: int) -> Level:
        emu = size * EMU_PER_PT // 100

        def sp(v, default):
            kind, val = v
            if kind == "pts":
                return int(val)
            if kind == "pct":
                return int(emu * 1.2 * val)
            return default

        return Level(emu, sp(self.ln, int(emu * 1.2)), sp(self.bef, 0), sp(self.aft, 0), self.margin)


def _spacing(ppr, tag):
    if ppr is None:
        return None
    el = ppr.find(q("a:" + tag))
    if el is None:
        return None
    pts = el.find(q("a:spcPts"))
    if pts is not None:
        return ("pts", int(pts.get("val")) * EMU_PER_PT / 100)
    pct = el.find(q("a:spcPct"))
    if pct is not None:
        val = pct.get("val", "100000")
        return ("pct", float(val[:-1]) / 100 if val.endswith("%") else int(val) / 100000)
    return None


def _first(chain, fn):
    for el in chain:
        v = fn(el)
        if v is not None:
            return v
    return None


def _defrpr_sz(ppr):
    if ppr is None:
        return None
    d = ppr.find(q("a:defRPr"))
    return int(d.get("sz")) if d is not None and d.get("sz") else None


@dataclass
class Styles:
    """The inheritance a sample slide's boxes walk (D12 donor run, effective size)."""

    layout_el: object
    master_el: object
    default_style: object  # presentation p:defaultTextStyle

    def ph_chain(self, sp, level: int):
        """a:lvlNpPr elements a placeholder inherits, nearest first: layout placeholder, master placeholder, master
        title or body text style."""
        ph = ph_of(sp)
        t, idx = ph_type(ph), ph.get("idx")
        out = []
        lay_sp = _match_ph(self.layout_el, t, idx)
        if lay_sp is not None:
            out.append(lvl_ppr(_lst(lay_sp), level))
        m_sp = find_master_ph(self.master_el, t)
        if m_sp is not None:
            out.append(lvl_ppr(_lst(m_sp), level))
        tx = self.master_el.find(q("p:txStyles"))
        if tx is not None:
            style = tx.find(q("p:titleStyle")) if t in ("title", "ctrTitle") else tx.find(q("p:bodyStyle"))
            out.append(lvl_ppr(style, level))
        return out

    def chain(self, sp, level: int):
        """The inherited a:lvlNpPr chain after the box's own list style."""
        if ph_of(sp) is not None:
            return self.ph_chain(sp, level)
        return [lvl_ppr(self.default_style, level)]


def _lst(sp):
    tx = None if sp is None else sp.find(q("p:txBody"))
    return None if tx is None else tx.find(q("a:lstStyle"))


def _match_ph(root, t, idx):
    """The placeholder on a layout (or master) that a slide placeholder inherits: same idx, else same type."""
    if root is None:
        return None
    phs = placeholders(root)
    if idx is not None:
        for sp, ph in phs:
            if ph.get("idx") == idx:
                return sp
    for sp, ph in phs:
        if ph_type(ph) == t:
            return sp
    return None


def level_spec(sp, styles: Styles, para, run, level: int) -> LevelSpec:
    """A paragraph level's written properties: the run's size, then the paragraph's, the box's list style, the
    inheritance (D12 donor run order), else 18 pt; spacing and margin from the paragraph, then the same chain."""
    ppr = None if para is None else para.find(q("a:pPr"))
    own = [lvl_ppr(_lst(sp), level)]
    inherited = styles.chain(sp, level)
    rpr = None if run is None else run.find(q("a:rPr"))
    size = int(rpr.get("sz")) if rpr is not None and rpr.get("sz") else None
    if size is None:
        size = _first([ppr] + own + inherited, _defrpr_sz)
    size = size or DEF_SIZE
    chain = [ppr] + own + inherited
    vals = {tag: _first(chain, lambda e, t=tag: _spacing(e, t)) or ("", 0.0) for tag in ("lnSpc", "spcBef", "spcAft")}
    margin = _first(chain, lambda e: int(e.get("marL")) if e is not None and e.get("marL") is not None else None) or 0
    return LevelSpec(size, vals["lnSpc"], vals["spcBef"], vals["spcAft"], max(margin, 0))


def level2_ppr(sp, styles: Styles):
    """D12: the box's level-2 paragraph properties, the box's own list style first, then its inheritance; None when
    neither defines them."""
    for e in [lvl_ppr(_lst(sp), 2)] + styles.chain(sp, 2):
        if e is not None and (len(e) or e.attrib):
            return e
    return None


def level2_written(sp, styles: Styles, para):
    """The exact a:pPr a written level-2 paragraph carries (D12 text, size budget R3-1): the box's level-2 properties
    resolved to an a:pPr with lvl="1" when defined, else the donor paragraph's a:pPr with lvl="1"."""
    src = level2_ppr(sp, styles)
    if src is None:
        src = None if para is None else para.find(q("a:pPr"))
    el = copy.deepcopy(src) if src is not None else etree.Element(q("a:pPr"))
    el.tag = q("a:pPr")
    el.set("lvl", "1")
    return el


def body_attrs(sp, styles: Styles):
    """bodyPr attributes and the autofit child, the box's own first, then (for a placeholder) the layout's and
    master's placeholder."""
    els = [sp]
    if ph_of(sp) is not None:
        ph = ph_of(sp)
        els.append(_match_ph(styles.layout_el, ph_type(ph), ph.get("idx")))
        els.append(find_master_ph(styles.master_el, ph_type(ph)))
    attrs: dict[str, str] = {}
    autofit = None
    for e in els:
        if e is None:
            continue
        tx = e.find(q("p:txBody"))
        bp = None if tx is None else tx.find(q("a:bodyPr"))
        if bp is None:
            continue
        for k, v in bp.attrib.items():
            attrs.setdefault(k, v)
        if autofit is None:
            for child in bp:
                if child.tag in (q("a:noAutofit"), q("a:normAutofit"), q("a:spAutoFit")):
                    autofit = etree.QName(child).localname
                    break
    return attrs, autofit


def unmodelled_reason(attrs, autofit, turned: bool) -> str:
    """Why a sample-route box cannot be estimated. Unlike D5 on the layout route, a box with shape autofit is
    estimated against its drawn box and a box with wrapping off as single lines against its drawn width (Fable's
    call, 2026-11-01, spec D12 fit); rotated or flipped boxes, vertical text and columns stay unmodelled."""
    if turned:
        return "rotated or flipped"
    if attrs.get("vert", "horz") in UNMODELLED_VERT:
        return "vertical text"
    if int(attrs.get("numCol", "1") or 1) > 1:
        return "columns in box"
    return ""


def insets(attrs) -> tuple[int, int, int, int]:
    return (
        int(attrs.get("lIns", DEF_LR_INS)),
        int(attrs.get("rIns", DEF_LR_INS)),
        int(attrs.get("tIns", DEF_TB_INS)),
        int(attrs.get("bIns", DEF_TB_INS)),
    )


def decorated(el) -> bool:
    """A shape with a fill or a line of its own (explicit, or from its theme style reference)."""
    tag = etree.QName(el).localname
    if tag == "pic":
        return True
    if tag == "grpSp":
        return True
    pr = el.find(q("p:spPr"))
    style = el.find(q("p:style"))
    fill = line = False
    if pr is not None:
        fill = any(pr.find(q(t)) is not None for t in FILL_TAGS)
        ln = pr.find(q("a:ln"))
        if ln is not None:
            line = ln.find(q("a:noFill")) is None and (len(ln) > 0 or ln.get("w") is not None)
        no_fill = pr.find(q("a:noFill")) is not None
    else:
        no_fill = False
    if style is not None:
        fr, lr = style.find(q("a:fillRef")), style.find(q("a:lnRef"))
        if not fill and not no_fill and fr is not None and fr.get("idx", "0") != "0":
            fill = True
        ln = pr.find(q("a:ln")) if pr is not None else None
        if not line and lr is not None and lr.get("idx", "0") != "0" and (ln is None or ln.find(q("a:noFill")) is None):
            line = True
    return fill or line


# ---------------------------------------------------------------------------------------------
# what a sample slide holds


@dataclass(frozen=True)
class SBox:
    sid: int
    x: int
    y: int
    cx: int
    cy: int
    text: str
    size: int  # donor run's effective size
    placeholder: bool
    decorated: bool
    unmodelled: str  # why the fit estimate cannot model this box; "" when it can
    nowrap: bool  # wrapping off: each paragraph is one line against the drawn width
    ins: tuple[int, int, int, int]  # l, r, t, b
    lvl1: LevelSpec
    lvl2: LevelSpec
    lvl2_inherited: bool  # the box or its inheritance defines level-2 properties (level-2 paragraphs carry them)
    ppr1: int  # bytes of the a:pPr a level-1 paragraph carries
    ppr2: int  # bytes of the a:pPr a level-2 paragraph carries
    rpr: int  # bytes of the donor a:rPr every written run carries

    @property
    def area(self) -> int:
        return self.cx * self.cy

    def fit_at(self, box=None, size1: int | None = None, size2: int | None = None) -> Fit | None:
        """D5 estimate inputs for this box (or the given slide-space box with this box's insets) at given sizes."""
        if self.unmodelled:
            return None
        _, _, cx, cy = box or (self.x, self.y, self.cx, self.cy)
        l, r, t, b = self.ins
        return Fit(cx - l - r, cy - t - b, (self.lvl1.at(size1 or self.lvl1.size), self.lvl2.at(size2 or self.lvl2.size)), self.nowrap)


@dataclass(frozen=True)
class Sample:
    k: int  # 1-based position of the slide in the template
    id: str  # "s<k>", the override id
    part: str  # slide part name
    layout: str  # layout part name
    usable: bool
    reason: str  # why not usable, "" when usable
    design: bool  # carries design of its own (D11)
    title: tuple[int, ...]  # title region shape ids in reading order; the first is the destination
    title_box: tuple[int, int, int, int]  # the union of the region's boxes, slide space
    labels: tuple[int, ...]
    bodies: tuple[int, ...]  # body box shape ids in reading order
    subtitle: int | None  # the body box with the largest area
    slots: tuple[tuple[int, ...], ...]  # list slot groups, each in reading order
    classes: tuple[str, ...]
    boxes: tuple[SBox, ...]  # every text box with its measure
    words: str  # the first words of the sample title, for the picker
    turned: bool  # a box sits inside a rotated or flipped shape or group
    nbytes: int  # the slide part's size
    nshapes: int  # shapes in the slide's tree
    footer_bytes: int  # an upper bound on the footers the fill may add to a copy (the D12 size budget)
    slide: tuple[int, int] = (0, 0)  # slide width and height, EMU (QA round 1 readability bars)
    leaves: tuple = ()  # QA round 2: every non-group shape (Leaf), for the clearing and the R3 grid
    groups: tuple = ()  # QA round 2: every group (GroupT), for growing a grouped body
    fixed: tuple = ()  # QA round 2 R3: drawn bounds of the layout's and master's visible non-placeholder shapes
    footers: tuple = ()  # QA round 2 R3: every box a rebuilt footer can take (an upper bound)
    error: str = ""  # code review F2: why reading this slide failed (reason "unreadable"); "" when it read

    def box(self, sid: int) -> SBox:
        return next(b for b in self.boxes if b.sid == sid)


def _reading(boxes):
    return sorted(boxes, key=lambda b: (b.y, b.x))


def _one_word(text: str) -> bool:
    t = text.strip()
    return len(t) <= 12 or not re.search(r"\s", t)


def _same_line(a, b, lh: float) -> bool:
    ca, cb = a.y + a.cy / 2, b.y + b.cy / 2
    gap = max(a.x, b.x) - min(a.x + a.cx, b.x + b.cx)
    return abs(ca - cb) <= lh / 2 and gap <= lh


def _stacked(a, b, lh: float) -> bool:
    overlap = min(a.x + a.cx, b.x + b.cx) - max(a.x, b.x)
    narrow = min(a.cx, b.cx)
    gap = max(a.y, b.y) - min(a.y + a.cy, b.y + b.cy)
    return narrow > 0 and overlap >= narrow / 2 and gap <= lh / 2


def title_region(boxes, turned_ids: set[int]):
    """D12 logical title: the anchor (largest effective size, then top-most, then left-most), then fragments chained
    from it. Returns the region's boxes in reading order."""
    if not boxes:
        return []
    anchor = sorted(boxes, key=lambda b: (-b.size, b.y, b.x))[0]
    lh = 1.2 * anchor.size * EMU_PER_PT / 100
    region = [anchor]
    rest = [b for b in boxes if b is not anchor]
    grew = True
    while grew:
        grew = False
        for b in list(rest):
            if abs(b.size - anchor.size) > 0.1 * anchor.size or not _one_word(b.text) or b.sid in turned_ids:
                continue
            if any(_same_line(b, r, lh) or _stacked(b, r, lh) for r in region):
                region.append(b)
                rest.remove(b)
                grew = True
    return _reading(region)


def union(boxes) -> tuple[int, int, int, int]:
    x1 = min(b.x for b in boxes)
    y1 = min(b.y for b in boxes)
    x2 = max(b.x + b.cx for b in boxes)
    y2 = max(b.y + b.cy for b in boxes)
    return x1, y1, x2 - x1, y2 - y1


def is_label(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _LABEL.match(t):
        return True
    return len(t) == 1 and not t.isalnum()


def slot_groups(bodies, sw: int, sh: int) -> list[tuple]:
    """D12 list slots: 2 or more body boxes with the same effective size, widths within 10%, and a shared top or
    left edge within 2% of the slide size. Rows read top then left; a shared left edge reads top to bottom."""
    out = []
    by_size: dict[int, list] = {}
    for b in bodies:
        by_size.setdefault(b.size, []).append(b)
    for same in by_size.values():
        for edge, tol in (("y", 0.02 * sh), ("x", 0.02 * sw)):
            pool = sorted(same, key=lambda b: (getattr(b, edge), b.x if edge == "y" else b.y))
            clusters: list[list] = []
            for b in pool:
                if clusters and abs(getattr(b, edge) - getattr(clusters[-1][0], edge)) <= tol:
                    clusters[-1].append(b)
                else:
                    clusters.append([b])
            for cl in clusters:
                cl = sorted(cl, key=lambda b: b.cx)
                groups: list[list] = []
                for b in cl:
                    if groups and b.cx <= groups[-1][0].cx * 1.1:
                        groups[-1].append(b)
                    else:
                        groups.append([b])
                for g in groups:
                    if len(g) >= 2:
                        order = sorted(g, key=lambda b: (b.y, b.x)) if edge == "y" else sorted(g, key=lambda b: (b.y,))
                        ids = tuple(b.sid for b in order)
                        if ids not in out:
                            out.append(ids)
    return out


def _overlap_x(a, b) -> bool:
    return not (a.x + a.cx <= b.x or b.x + b.cx <= a.x)


def instruction(texts: list[str]) -> bool:
    low = [t.lower() for t in texts]
    for phrase in INSTRUCTION_PHRASES:
        pat = re.compile((r"(?<![\w])" if phrase[0].isascii() else "") + re.escape(phrase) + (r"(?![\w])" if phrase[-1].isascii() else ""))
        if any(pat.search(t) for t in low):
            return True
    return sum(len(_HEX.findall(t)) for t in texts) >= 3


def closing(title_text: str, whole: str) -> bool:
    t = " ".join(_PUNCT.sub(" ", title_text.lower()).split())
    return len(whole) < 80 and any(t.startswith(s) for s in CLOSING_STARTS)


# ---------------------------------------------------------------------------------------------
# design of its own (D11)


def _canon_bg(bg, rels) -> str | None:
    """A background as a string that compares fills, with picture references replaced by the picture's bytes."""
    if bg is None:
        return None
    el = copy.deepcopy(bg)
    for e in el.iter():
        for k, v in list(e.attrib.items()):
            if k.startswith("{%s}" % R_NS):
                rel = rels.get(v)
                blob = rel.target_part.blob if rel is not None and not rel.is_external else b""
                e.set(k, hashlib.sha256(blob).hexdigest())
    return etree.tostring(el, method="c14n")


def resolved_bg(el, part):
    bg = el.find(q("p:cSld")).find(q("p:bg"))
    return None if bg is None else _canon_bg(bg, part.rels)


def covered(rects, sw: int, sh: int, n: int = 160) -> float:
    """Share of the slide area the union of rectangles covers, on an n by n grid."""
    if not rects or sw <= 0 or sh <= 0:
        return 0.0
    hit = [[False] * n for _ in range(n)]
    for x, y, cx, cy in rects:
        x0, x1 = max(0, int(x / sw * n)), min(n, int((x + cx) / sw * n + 0.999))
        y0, y1 = max(0, int(y / sh * n)), min(n, int((y + cy) / sh * n + 0.999))
        for j in range(y0, y1):
            row = hit[j]
            for i in range(x0, x1):
                row[i] = True
    return sum(sum(r) for r in hit) / (n * n)


def decoration_rects(sptree) -> list:
    """Slide-space boxes of non-placeholder pictures, groups and shapes with a fill or line (text shapes with a
    fill count); placeholders never count (D11)."""
    out = []
    for w in walk(sptree):
        el = w.el
        tag = etree.QName(el).localname
        if tag == "sp" and ph_of(el) is not None:
            continue
        if tag == "pic":
            nv = el.find(q("p:nvPicPr"))
            if nv is not None and nv.find(q("p:nvPr")) is not None and nv.find(q("p:nvPr")).find(q("p:ph")) is not None:
                continue
        if tag in ("pic", "grpSp") or (tag in ("sp", "cxnSp") and decorated(el)):
            box = _local_box(el)
            if box is not None:
                out.append(to_slide(box, w.chain))
    return out


# ---------------------------------------------------------------------------------------------
# shapes on the copy (QA round 2: R3 free space, R5 rectangular backings)

RECT_PRESETS = {"rect", "roundRect", "snip1Rect", "snip2SameRect", "round1Rect", "round2SameRect", "flowChartProcess",
                "flowChartAlternateProcess"}


_INT = re.compile(r"[+-]?[0-9]+")


def _coord(v) -> int | None:
    """A custom path point coordinate as a plain integer; None for a guide name or anything else unresolved."""
    return int(v) if v is not None and _INT.fullmatch(v.strip()) else None


def is_rect_geom(el) -> bool:
    """R5: a rectangular preset, or a custGeom with one closed path of one moveTo and three or four lnTo visiting the
    four corners of its own bounding box in perimeter order (no curve, no diagonal, no crossing)."""
    pr = el.find(q("p:spPr"))
    if pr is None:
        return False
    pg = pr.find(q("a:prstGeom"))
    if pg is not None:
        return pg.get("prst") in RECT_PRESETS
    cg = pr.find(q("a:custGeom"))
    lst = None if cg is None else cg.find(q("a:pathLst"))
    paths = [] if lst is None else lst.findall(q("a:path"))
    if len(paths) != 1:
        return False
    cmds = [c for c in paths[0] if isinstance(c.tag, str)]
    names = [etree.QName(c).localname for c in cmds]
    closed = names[-1:] == ["close"]
    if closed:
        names, cmds = names[:-1], cmds[:-1]
    if not names or names[0] != "moveTo" or any(n != "lnTo" for n in names[1:]) or len(names) not in (4, 5):
        return False
    pts = []
    for c in cmds:
        pt = c.find(q("a:pt"))
        if pt is None:
            return False
        x, y = _coord(pt.get("x")), _coord(pt.get("y"))
        if x is None or y is None:
            return False  # a guide name (w, h, a named guide) or an unreadable value: not a backing (code review F2)
        pts.append((x, y))
    if len(pts) == 5:
        if pts[4] != pts[0]:
            return False
        pts = pts[:4]
    elif not closed:
        return False
    xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
    if len(xs) != 2 or len(ys) != 2 or set(pts) != {(x, y) for x in xs for y in ys}:
        return False
    return all(a[0] == b[0] or a[1] == b[1] for a, b in zip(pts, pts[1:] + pts[:1]))


def backing_shape(el, turned: bool) -> bool:
    """R5 backing test on a text-free p:sp: rectangular geometry (is_rect_geom), unrotated and unflipped (its groups
    too), and filled with a:solidFill, or with a:noFill and a line. A picture, gradient or pattern fill never is."""
    if turned or not is_rect_geom(el):
        return False
    pr = el.find(q("p:spPr"))
    if pr.find(q("a:solidFill")) is not None:
        return True
    ln = pr.find(q("a:ln"))
    has_line = ln is not None and ln.find(q("a:noFill")) is None and (len(ln) > 0 or ln.get("w") is not None)
    return pr.find(q("a:noFill")) is not None and has_line


def _rot(el) -> int:
    x = _xfrm_el(el)
    return int(x.get("rot", "0") or 0) if x is not None else 0


def _rotate(pts, centre, rot: int):
    if rot % 21600000 == 0:
        return pts
    import math

    a = math.radians(rot / 60000)
    c, s = math.cos(a), math.sin(a)
    cx, cy = centre
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


def _flips(el) -> tuple[bool, bool]:
    x = _xfrm_el(el)
    if x is None:
        return False, False
    return x.get("flipH") in ("1", "true"), x.get("flipV") in ("1", "true")


def occ_box(el, ancestors) -> tuple[int, int, int, int] | None:
    """R3: the axis-aligned slide-space bounds of a drawn shape, its own rotation and its groups' included. Each group
    maps its children to its parent's space, mirrors them about its centre when flipped (code review F3), then rotates
    them about its centre. A shape's own flip leaves its bounds unchanged."""
    local = _local_box(el)
    if local is None:
        return None
    x, y, cx, cy = local
    pts = _rotate([(x, y), (x + cx, y), (x, y + cy), (x + cx, y + cy)], (x + cx / 2, y + cy / 2), _rot(el))
    for g in ancestors:  # innermost first
        xf = group_xf(g)
        if xf is not None:
            pts = [xf.apply(px, py) for px, py in pts]
        gl = _local_box(g)
        if gl is None:
            continue
        mx, my = gl[0] + gl[2] / 2, gl[1] + gl[3] / 2
        fh, fv = _flips(g)
        if fh or fv:
            pts = [(2 * mx - px if fh else px, 2 * my - py if fv else py) for px, py in pts]
        if _rot(g):
            pts = _rotate(pts, (mx, my), _rot(g))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return round(min(xs)), round(min(ys)), round(max(xs) - min(xs)), round(max(ys) - min(ys))


@dataclass(frozen=True)
class Leaf:
    """A non-group shape of a sample slide, as the copy will hold it."""

    sid: int | None
    tag: str  # sp, pic, cxnSp, graphicFrame, contentPart
    qbox: tuple | None  # slide-space box without rotation, as the Q1 clearing measures it
    occ: tuple | None  # drawn bounds, rotation included (R3 grid)
    local: tuple | None  # its own a:xfrm box
    hidden: bool
    text: bool
    deco: bool
    ph: str  # placeholder type, "" for a free shape
    rect: bool  # passes the R5 backing test: rectangular, unrotated, solid fill (or no fill and a line)
    groups: tuple[int, ...]  # enclosing group shape ids, innermost first


@dataclass(frozen=True)
class GroupT:
    sid: int | None
    local: tuple | None  # off and ext
    choff: tuple | None
    chext: tuple | None
    groups: tuple[int, ...]  # enclosing group shape ids, innermost first


def _group_t(g, parents) -> GroupT:
    x = _xfrm_el(g)
    get = (lambda t: None if x is None else x.find(q("a:" + t)))
    co, ce = get("chOff"), get("chExt")
    return GroupT(shape_id(g), _local_box(g), None if co is None else (int(co.get("x", 0)), int(co.get("y", 0))),
                  None if ce is None else (int(ce.get("cx", 0)), int(ce.get("cy", 0))), parents)


def shape_tree_leaves(sptree, styles=None):
    """Leaves and groups of a shape tree (R3, R5). A placeholder with no a:xfrm takes its layout's or master's box."""
    leaves, groups = [], []
    for w in walk(sptree):
        el = w.el
        tag = etree.QName(el).localname
        anc = [a for a in el.iterancestors() if a.tag == q("p:grpSp")]
        gids = tuple(shape_id(a) for a in anc)
        if tag == "grpSp":
            groups.append(_group_t(el, gids))
            continue
        ph = ph_of(el) if tag == "sp" else None
        local = _local_box(el)
        qbox = to_slide(local, w.chain) if local is not None else None
        occ = occ_box(el, anc)
        if local is None and ph is not None and styles is not None:
            src = _match_ph(styles.layout_el, ph_type(ph), ph.get("idx"))
            if src is None:
                src = find_master_ph(styles.master_el, ph_type(ph))
            if src is not None and _local_box(src) is not None:
                qbox = occ = _local_box(src)
        leaves.append(Leaf(shape_id(el), tag, qbox, occ, local, w.hidden, tag == "sp" and has_text(el), decorated(el),
                           ph_type(ph) if ph is not None else "", tag == "sp" and backing_shape(el, w.turned), gids))
    return tuple(leaves), tuple(groups)


def fixed_boxes(tree) -> list:
    """Drawn bounds of a layout's or master's visible non-placeholder shapes (R3)."""
    out = []
    for w in walk(tree):
        el = w.el
        tag = etree.QName(el).localname
        if tag == "grpSp" or w.hidden:
            continue
        if tag == "sp" and ph_of(el) is not None:
            continue
        if tag == "pic":
            nv = el.find(q("p:nvPicPr"))
            if nv is not None and nv.find(q("p:nvPr")) is not None and nv.find(q("p:nvPr")).find(q("p:ph")) is not None:
                continue
        b = occ_box(el, [a for a in el.iterancestors() if a.tag == q("p:grpSp")])
        if b is not None:
            out.append(b)
    return out


def footer_boxes(tree, layout_el=None, master_el=None) -> list:
    """Slide-space boxes of the footer placeholders in a tree (dt, ftr, sldNum); one with no a:xfrm takes its
    layout's, then its master's box."""
    out = []
    for w in walk(tree):
        el = w.el
        if etree.QName(el).localname != "sp" or ph_of(el) is None or ph_type(ph_of(el)) not in FOOTER_TYPES:
            continue
        local = _local_box(el)
        if local is None:
            t = ph_type(ph_of(el))
            src = _match_ph(layout_el, t, ph_of(el).get("idx")) if layout_el is not None else None
            if src is None and master_el is not None:
                src = find_master_ph(master_el, t)
            local = _local_box(src) if src is not None else None
            if local is not None:
                out.append(local)
            continue
        out.append(to_slide(local, w.chain))
    return out


# ---------------------------------------------------------------------------------------------


def read_sample(k: int, slide, styles: Styles, sw: int, sh: int, layout_bg, master_bg, layout_master_cover: float,
                fixed=(), footers=(), deck_footers=None) -> Sample:
    el = slide._element
    part = slide.part
    csld = el.find(q("p:cSld"))
    sptree = csld.find(q("p:spTree"))
    walked = walk(sptree)
    nshapes = sum(1 for w in walked)
    graphic = any(etree.QName(w.el).localname == "graphicFrame" for w in walked)
    boxes: list[SBox] = []
    hidden_ids: set[int] = set()
    turned_ids: set[int] = set()
    all_text: list[str] = []
    for w in walked:
        sp = w.el
        if etree.QName(sp).localname != "sp" or not has_text(sp):
            continue
        ph = ph_of(sp)
        if ph is not None and ph_type(ph) in FOOTER_TYPES:
            continue
        sid = shape_id(sp)
        if sid is None:
            continue
        text = text_of(sp)
        all_text.append(text)
        if w.hidden:
            hidden_ids.add(sid)
            continue
        local = _local_box(sp)
        if local is None and ph is not None:
            src = _match_ph(styles.layout_el, ph_type(ph), ph.get("idx"))
            local = _local_box(src) if src is not None else None
            if local is None:
                m = find_master_ph(styles.master_el, ph_type(ph))
                local = _local_box(m) if m is not None else None
        if local is None:
            continue
        x, y, cx, cy = to_slide(local, w.chain)
        para, run = donor(sp)
        lvl = _lvl(para)
        l1 = level_spec(sp, styles, para, run, lvl)
        # a level-2 paragraph carries <a:pPr lvl="1"/> when the box or its inheritance defines level 2, else the
        # donor's a:pPr with lvl="1"; its runs carry the donor's a:rPr either way (D12 text)
        l2_def = level2_ppr(sp, styles) is not None
        l2 = level_spec(sp, styles, None if l2_def else para, run, 2)
        attrs, autofit = body_attrs(sp, styles)
        why = unmodelled_reason(attrs, autofit, w.turned)
        if w.turned:
            turned_ids.add(sid)
        ppr = None if para is None else para.find(q("a:pPr"))
        rpr = None if run is None else run.find(q("a:rPr"))
        ppr1 = len(etree.tostring(ppr)) if ppr is not None else 0
        ppr2 = len(etree.tostring(level2_written(sp, styles, para)))
        boxes.append(SBox(sid, x, y, cx, cy, text, l1.size, ph is not None, decorated(sp), why, attrs.get("wrap") == "none", insets(attrs), l1, l2, l2_def,
                          ppr1, ppr2, len(etree.tostring(rpr)) if rpr is not None else 0))
    hidden_slide = el.get("show") in ("0", "false")
    region = title_region(boxes, turned_ids)
    region_ids = {b.sid for b in region}
    labels = [b for b in boxes if b.sid not in region_ids and is_label(b.text)]
    label_ids = {b.sid for b in labels}
    bodies = _reading([b for b in boxes if b.sid not in region_ids and b.sid not in label_ids])
    reason = ""
    title_text = " ".join(b.text.strip() for b in region)
    whole = " ".join(t.strip() for t in all_text)
    if hidden_slide:
        reason = "hidden"
    elif not region:
        reason = "no title"
    elif graphic:
        reason = "chart, table or diagram"
    elif instruction(all_text):
        reason = "instructions"
    elif closing(title_text, whole):
        reason = "closing"
    tbox = union(region) if region else (0, 0, 0, 0)
    tarea = tbox[2] * tbox[3]
    classes = []
    slots = slot_groups(bodies, sw, sh)
    if region:
        if not bodies or sum(b.area for b in bodies) < 0.1 * tarea:
            classes.append("section")
        two = (len(bodies) == 2 and not _overlap_x(bodies[0], bodies[1])) or any(
            len(g) == 2 and not _overlap_x(*[next(b for b in bodies if b.sid == s) for s in g]) for g in slots
        )
        if two:
            classes.append("two")
        if bodies:
            classes.append("content")
    subtitle = max(bodies, key=lambda b: (b.area, -b.y, -b.x)).sid if bodies else None
    # D11 design of its own
    own_bg = resolved_bg(el, part)
    design = False
    if own_bg is not None and own_bg != (layout_bg if layout_bg is not None else master_bg):
        design = True
    if boxes and all(not b.placeholder for b in boxes):
        design = True
    if covered(decoration_rects(sptree), sw, sh) >= 0.15 and layout_master_cover < 0.05:
        design = True
    words = " ".join(title_text.split())
    leaves, groups = shape_tree_leaves(sptree, styles)
    return Sample(
        k=k,
        id=f"s{k}",
        part=str(part.partname),
        layout=str(slide.slide_layout.part.partname),
        usable=not reason,
        reason=reason,
        design=design,
        title=tuple(b.sid for b in region),
        title_box=tbox,
        labels=tuple(b.sid for b in _reading(labels)),
        bodies=tuple(b.sid for b in bodies),
        subtitle=subtitle,
        slots=tuple(slots),
        classes=tuple(classes),
        boxes=tuple(boxes),
        words=words[:24] + ("…" if len(words) > 24 else ""),
        turned=bool(turned_ids),
        nbytes=len(etree.tostring(el)),
        nshapes=nshapes,
        footer_bytes=footer_budget(walked, styles.layout_el, deck_footers or {}),
        slide=(sw, sh),
        leaves=leaves,
        groups=groups,
        fixed=tuple(fixed) if el.get("showMasterSp") not in ("0", "false") else (),
        footers=tuple(footers),
    )


FOOTER_SLACK = 512  # per footer type: an a:xfrm the fill may add, a new shape id, a slide number's digits


def footer_sizes(walked) -> dict[str, int]:
    """The largest footer placeholder of each type among walked shapes, serialised bytes."""
    out: dict[str, int] = {}
    for w in walked:
        if etree.QName(w.el).localname == "sp" and ph_of(w.el) is not None and ph_type(ph_of(w.el)) in FOOTER_TYPES:
            t = ph_type(ph_of(w.el))
            out[t] = max(out.get(t, 0), len(etree.tostring(w.el)))
    return out


def footer_budget(walked, layout_el, deck: dict[str, int]) -> int:
    """D12 limits, code review E1: an upper bound on the footers a copy can receive, whichever D4 step supplies each
    type: per type, the largest of this slide's own, any slide's in the deck (step 1 borrows from another slide) and
    the layout's (step 3), plus slack for what the fill adds."""
    own = footer_sizes(walked)
    lay: dict[str, int] = {}
    for sp, ph in placeholders(layout_el):
        if ph_type(ph) in FOOTER_TYPES:
            lay[ph_type(ph)] = max(lay.get(ph_type(ph), 0), len(etree.tostring(sp)))
    return sum(max(own.get(t, 0), deck.get(t, 0), lay.get(t, 0)) + FOOTER_SLACK
               for t in FOOTER_TYPES if t in own or t in deck or t in lay)


def read_samples(prs) -> tuple[Sample, ...]:
    sw, sh = int(prs.slide_width or 9144000), int(prs.slide_height or 6858000)
    default_style = prs.part._element.find(q("p:defaultTextStyle"))
    out = []
    cover_cache: dict[str, float] = {}
    fixed_cache: dict[str, list] = {}
    # R3: every box a rebuilt footer can take on a copy: footer placeholders of every slide on the same layout (D4
    # step 1's examples), of the layout and of its master (an upper bound, so the grid never under-counts)
    foot: dict[str, list] = {}
    broken: dict[int, str] = {}  # code review F2: a slide whose reading raised is unusable, never the whole template
    deck_footers: dict[str, int] = {}  # E1: the largest footer of each type on any slide (D4 step 1 can borrow it)
    for k, slide in enumerate(prs.slides, start=1):
        try:
            # F1: the slides are read as the copies will hold them (this Presentation is the reader's own)
            normalise_alternates(slide._element.find(q("p:cSld")))
            lay = slide.slide_layout
            tree = slide._element.find(q("p:cSld")).find(q("p:spTree"))
            foot.setdefault(str(lay.part.partname), []).extend(footer_boxes(tree, lay._element, lay.slide_master._element))
            for t, n in footer_sizes(walk(tree)).items():
                deck_footers[t] = max(deck_footers.get(t, 0), n)
        except MemoryError:
            raise
        except Exception as e:
            broken[k] = _why(e)
    for k, slide in enumerate(prs.slides, start=1):
        if k in broken:
            out.append(unreadable(k, slide, broken[k]))
            continue
        try:
            layout = slide.slide_layout
            master = layout.slide_master
            styles = Styles(layout._element, master._element, default_style)
            lid = str(layout.part.partname)
            lay_tree = layout._element.find(q("p:cSld")).find(q("p:spTree"))
            mas_tree = master._element.find(q("p:cSld")).find(q("p:spTree"))
            if lid not in cover_cache:
                rects = decoration_rects(lay_tree)
                fixed = fixed_boxes(lay_tree)
                if layout._element.get("showMasterSp") not in ("0", "false"):
                    rects += decoration_rects(mas_tree)
                    fixed += fixed_boxes(mas_tree)
                fixed_cache[lid] = fixed
                foot.setdefault(lid, []).extend(footer_boxes(lay_tree, None, master._element) + footer_boxes(mas_tree))
                cover_cache[lid] = covered(rects, sw, sh)
            layout_bg = resolved_bg(layout._element, layout.part)
            master_bg = resolved_bg(master._element, master.part)
            out.append(read_sample(k, slide, styles, sw, sh, layout_bg, master_bg, cover_cache[lid], fixed_cache[lid],
                                   foot.get(lid, []), deck_footers))
        except MemoryError:
            raise
        except Exception as e:
            out.append(unreadable(k, slide, _why(e)))
    return tuple(out)


def _why(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:200]


def unreadable(k: int, slide, why: str) -> Sample:
    """Code review F2: a sample slide whose reading raised (a malformed attribute, an unresolved reference). It is
    never usable, so neither route uses it, and why it failed stays in the template info (Sample.error)."""
    def name(get):
        try:
            return str(get())
        except Exception:
            return ""

    return Sample(k=k, id=f"s{k}", part=name(lambda: slide.part.partname),
                  layout=name(lambda: slide.slide_layout.part.partname), usable=False, reason="unreadable",
                  design=False, title=(), title_box=(0, 0, 0, 0), labels=(), bodies=(), subtitle=None, slots=(),
                  classes=(), boxes=(), words="", turned=False, nbytes=0, nshapes=0, footer_bytes=0, error=why)


def usable(samples) -> list[Sample]:
    return [s for s in samples if s.usable]


def sample_route_available(samples) -> bool:
    """D11: at least one usable sample slide is compatible with a content slide (a title and a body destination)."""
    return any(s.usable and s.title and s.bodies for s in samples)


def sample_default(samples) -> bool:
    """D11 with QA round 2's R4: when both routes are available, the sample route is the default when at least half of
    the usable sample slides carry design of their own and at least 3 usable samples are content-compatible (a title
    and a body destination). A template with only the sample route uses it whatever this says (open_template)."""
    u = usable(samples)
    content = [s for s in u if s.title and s.bodies]
    return bool(u) and sum(1 for s in u if s.design) * 2 >= len(u) and len(content) >= 3


# ---------------------------------------------------------------------------------------------
# what a copy keeps (QA round 1 Q1 with round 2's R5), shared by the fill and the R3 grid

CHIP_SHARE = 0.08  # Q1: a cleared chip or backing under 8% of the slide area goes
BACKING_SHARE = 0.8  # a backing holds at least 80% of the text box's area


def box_of(b) -> tuple[int, int, int, int]:
    return b.x, b.y, b.cx, b.cy


def inside(inner, outer) -> float:
    """The share of inner's area that lies inside outer (slide-space boxes)."""
    ix = min(inner[0] + inner[2], outer[0] + outer[2]) - max(inner[0], outer[0])
    iy = min(inner[1] + inner[3], outer[1] + outer[3]) - max(inner[1], outer[1])
    a = inner[2] * inner[3]
    return (ix * iy) / a if ix > 0 and iy > 0 and a > 0 else 0.0


def dest_boxes(S: Sample, fills) -> list:
    """The boxes the Q1 'behind a destination' test reads: a joined title's widened box, every other destination's
    own sample box (a grown body box counts at its original size, R3)."""
    return [bf.box if bf.role == "title" and bf.box else box_of(S.box(bf.sid)) for bf in fills]


def clearing(S: Sample, fills, area: int) -> tuple[set, set]:
    """Q1 (with R5) on a copy of S: the shapes that go whole, and the decorated text shapes that keep their shape
    and lose their text. Title fragments and footer placeholders are handled apart by the fill."""
    fill_ids = {bf.sid for bf in fills}
    dests = dest_boxes(S, fills)
    cleared = [box_of(b) for b in S.boxes if b.sid not in fill_ids]
    frags = set(S.title[1:])

    def goes(box, backing: bool) -> bool:
        if box is None or box[2] * box[3] >= CHIP_SHARE * area:
            return False
        # behind a destination that kept its text: it backs the destination's box, or it lies under that box
        if any(inside(d, box) >= BACKING_SHARE or inside(box, d) >= BACKING_SHARE for d in dests):
            return False
        return not backing or any(inside(c, box) >= BACKING_SHARE for c in cleared)

    remove, clear = set(), set()
    for lf in S.leaves:
        if lf.tag != "sp" or lf.sid is None or lf.sid in fill_ids or lf.sid in frags or lf.ph in FOOTER_TYPES:
            continue
        if lf.text:
            if lf.ph or not lf.deco or goes(lf.qbox, False):
                remove.add(lf.sid)
            else:
                clear.add(lf.sid)
        elif not lf.ph and lf.deco and lf.rect and goes(lf.qbox, True):  # R5: only a rectangle is a backing
            remove.add(lf.sid)
    return remove, clear


# ---------------------------------------------------------------------------------------------
# growing a box inside its groups (D12 title widening, R3 grown body)


def grown_groups(chain, box):
    """The transforms each enclosing group takes so that its declared bounds hold a child box: chain is the
    enclosing groups' (off, ext, chOff, chExt) tuples innermost first, box the child's local box. Each group's child
    extent grows to hold the box at the group's own scale. Returns the new tuples, or None at the first group with
    no chOff or chExt (it cannot be grown)."""
    out = []
    for off, ext, choff, chext in chain:
        if choff is None or chext is None:
            return None
        (ox, oy), (ex, ey), (c0x, c0y), (cex, cey) = off, ext, choff, chext
        sx, sy = (ex / cex if cex else 1.0), (ey / cey if cey else 1.0)
        bx, by, bcx, bcy = box
        u0x, u0y = min(c0x, bx), min(c0y, by)
        u1x, u1y = max(c0x + cex, bx + bcx), max(c0y + cey, by + bcy)
        if (u0x, u0y, u1x, u1y) == (c0x, c0y, c0x + cex, c0y + cey):
            out.append((off, ext, choff, chext))
            box = (ox, oy, ex, ey)
            continue
        nox, noy = round(ox + (u0x - c0x) * sx), round(oy + (u0y - c0y) * sy)
        nex, ney = round((u1x - u0x) * sx), round((u1y - u0y) * sy)
        out.append(((nox, noy), (nex, ney), (u0x, u0y), (u1x - u0x, u1y - u0y)))
        box = (nox, noy, nex, ney)
    return out


def _xf_of(off, ext, choff, chext) -> Xf:
    (ox, oy), (ex, ey) = off, ext
    c0x, c0y = choff if choff is not None else (ox, oy)
    cex, cey = chext if chext is not None else (ex, ey)
    return Xf(ox, oy, ex / cex if cex else 1.0, ey / cey if cey else 1.0, c0x, c0y)


def grow_in_groups(S: Sample, moves) -> bool:
    """R3 grouped bodies: whether the shapes in moves, a list of (shape id, new slide-space box), can take their new
    boxes with each enclosing group grown by grown_groups (once, to hold all of them) while every other shape in those
    groups keeps its slide-space box exactly. The moved shapes must share one group chain (a body and its own backing
    in separate nested groups cannot both grow)."""
    leaves = {lf.sid: lf for lf in S.leaves}
    moved = [leaves.get(sid) for sid, _ in moves]
    if any(lf is None or lf.local is None for lf in moved):
        return False
    chain_ids = moved[0].groups
    if any(lf.groups != chain_ids for lf in moved):
        return False
    if not chain_ids:
        return True
    gt = {g.sid: g for g in S.groups}
    if any(g not in gt or gt[g].local is None for g in chain_ids):
        return False
    chain = [_chain_of(gt[g]) for g in chain_ids]
    old_xf = {g: _xf_of(*c) for g, c in zip(chain_ids, chain)}
    locals_ = [to_local(box, tuple(old_xf[g] for g in chain_ids)) for _, box in moves]
    x1 = min(b[0] for b in locals_)
    y1 = min(b[1] for b in locals_)
    x2 = max(b[0] + b[2] for b in locals_)
    y2 = max(b[1] + b[3] for b in locals_)
    new = grown_groups(chain, (x1, y1, x2 - x1, y2 - y1))
    if new is None:
        return False
    new_xf = dict(old_xf)
    new_xf.update({g: _xf_of(*c) for g, c in zip(chain_ids, new)})
    moved_ids = {sid for sid, _ in moves}
    outer = chain_ids[-1]

    def xfs(gids, table):
        return tuple(table.get(g) or _xf_of(*_chain_of(gt[g])) for g in gids)

    others = [(lf.local, lf.groups) for lf in S.leaves if lf.sid not in moved_ids and outer in lf.groups and lf.local]
    others += [(g.local, g.groups) for g in S.groups if outer in g.groups and g.sid not in chain_ids and g.local]
    for local, gids in others:
        if any(g not in gt for g in gids):
            return False
        if to_slide(local, xfs(gids, old_xf)) != to_slide(local, xfs(gids, new_xf)):
            return False
    return True


def _chain_of(g: GroupT):
    return (g.local[0], g.local[1]), (g.local[2], g.local[3]), g.choff, g.chext
