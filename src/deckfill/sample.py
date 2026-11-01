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


def read_sample(k: int, slide, styles: Styles, sw: int, sh: int, layout_bg, master_bg, layout_master_cover: float) -> Sample:
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
        footer_bytes=sum(len(etree.tostring(w.el)) for w in walked if etree.QName(w.el).localname == "sp"
                         and ph_of(w.el) is not None and ph_type(ph_of(w.el)) in FOOTER_TYPES)
        + sum(len(etree.tostring(sp)) for sp, ph in placeholders(styles.layout_el) if ph_type(ph) in FOOTER_TYPES),
        slide=(sw, sh),
    )


def read_samples(prs) -> tuple[Sample, ...]:
    sw, sh = int(prs.slide_width or 9144000), int(prs.slide_height or 6858000)
    default_style = prs.part._element.find(q("p:defaultTextStyle"))
    out = []
    cover_cache: dict[str, float] = {}
    for k, slide in enumerate(prs.slides, start=1):
        layout = slide.slide_layout
        master = layout.slide_master
        styles = Styles(layout._element, master._element, default_style)
        lid = str(layout.part.partname)
        if lid not in cover_cache:
            rects = decoration_rects(layout._element.find(q("p:cSld")).find(q("p:spTree")))
            if layout._element.get("showMasterSp") not in ("0", "false"):
                rects += decoration_rects(master._element.find(q("p:cSld")).find(q("p:spTree")))
            cover_cache[lid] = covered(rects, sw, sh)
        layout_bg = resolved_bg(layout._element, layout.part)
        master_bg = resolved_bg(master._element, master.part)
        out.append(read_sample(k, slide, styles, sw, sh, layout_bg, master_bg, cover_cache[lid]))
    return tuple(out)


def usable(samples) -> list[Sample]:
    return [s for s in samples if s.usable]


def sample_route_available(samples) -> bool:
    """D11: at least one usable sample slide is compatible with a content slide (a title and a body destination)."""
    return any(s.usable and s.title and s.bodies for s in samples)


def sample_default(samples) -> bool:
    """D11: the sample route is the default when at least half of the usable sample slides carry design of their own."""
    u = usable(samples)
    return bool(u) and sum(1 for s in u if s.design) * 2 >= len(u)
