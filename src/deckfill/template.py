"""read_template: open a template, classify its layouts (D3) and measure body boxes (D5)."""

from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass

from .errors import TemplateError
from .package import Package, load
from .xmlsafe import q

IGNORED_TYPES = {"dt", "ftr", "sldNum", "hdr", "pic", "chart", "tbl", "dgm", "media", "clipArt", "sldImg"}
FOOTER_TYPES = ("sldNum", "ftr", "dt")
TITLE_TYPES = {"title", "ctrTitle"}
BODY_TYPES = {"body", "obj"}  # plus a placeholder with no type (OOXML default is obj)
TYPED_CLASS = {
    "title": "title",
    "obj": "content",
    "tx": "content",
    "twoObj": "two",
    "twoTxTwoObj": "two",
    "twoColTx": "two",
    "secHead": "section",
    "titleOnly": "section",
}
UNMODELLED_VERT = {"vert", "vert270", "wordArtVert", "eaVert", "mongolianVert", "wordArtVertRtl"}

# OOXML defaults (EMU, hundredths of a point)
DEF_LR_INS = 91440
DEF_TB_INS = 45720
DEF_SZ = 1800
EMU_PER_PT = 12700


@dataclass(frozen=True)
class Level:
    size: int  # font size, EMU
    line: int  # line height, EMU
    before: int  # space before, EMU
    after: int  # space after, EMU
    margin: int  # left margin, EMU


@dataclass(frozen=True)
class Fit:
    """What the D5 estimate needs for one body box. None on a body means not modelled."""

    width: int  # text width inside insets, EMU
    height: int  # text height inside insets, EMU
    levels: tuple[Level, Level]
    nowrap: bool = False  # rev 8 sample route: wrapping off, one line per paragraph against the width


@dataclass(frozen=True)
class Body:
    idx: int
    x: int | None
    y: int | None
    cx: int | None
    cy: int | None
    fit: Fit | None
    why_unmodelled: str = ""

    @property
    def area(self) -> int:
        return (self.cx or 0) * (self.cy or 0)


@dataclass(frozen=True)
class Layout:
    id: str  # part name, stable across runs
    name: str
    master: int
    cls: str  # title, content, two, section, other
    title_idx: int | None
    subtitle_idx: int | None
    bodies: tuple[Body, ...]  # in XML order
    main_body: int | None  # largest body, ties leftmost
    columns: tuple[int, int] | None  # left and right body idx, when two bodies sit side by side
    footers: tuple[str, ...]  # footer placeholder types this layout defines

    def body(self, idx: int) -> Body:
        return next(b for b in self.bodies if b.idx == idx)


@dataclass(frozen=True)
class TemplateInfo:
    filename: str
    kind: str  # pptx, potx, ppsx
    masters: tuple[str, ...]
    layouts: tuple[Layout, ...]
    defaults: tuple[tuple[str, str | None], ...]  # class -> default layout id
    slide_count: int
    samples: tuple = ()  # rev 8: every sample slide, read by sample.read_samples (D12)
    routes: tuple[str, ...] = ("layout",)  # rev 8: the routes this template offers (D11)
    route: str = "layout"  # rev 8: the default route (D11)

    def layout(self, layout_id: str) -> Layout:
        for lay in self.layouts:
            if lay.id == layout_id:
                return lay
        raise KeyError(layout_id)

    def default(self, cls: str) -> str | None:
        return dict(self.defaults).get(cls)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["defaults"] = dict(self.defaults)
        return d


# ---------------------------------------------------------------------------------------------
# placeholder reading


def ph_of(sp):
    nv = sp.find(q("p:nvSpPr"))
    if nv is None:
        return None
    nvpr = nv.find(q("p:nvPr"))
    return None if nvpr is None else nvpr.find(q("p:ph"))


def ph_type(ph) -> str:
    return ph.get("type", "obj")


def ph_idx(ph) -> int:
    return int(ph.get("idx", "0"))


def placeholders(tree_root):
    """(sp, ph) for each placeholder shape in a slide, layout or master shape tree."""
    sptree = tree_root.find(q("p:cSld")).find(q("p:spTree"))
    out = []
    for sp in sptree:
        if sp.tag != q("p:sp"):
            continue
        ph = ph_of(sp)
        if ph is not None:
            out.append((sp, ph))
    return out


def master_type(t: str) -> str:
    if t in TITLE_TYPES:
        return "title"
    if t in FOOTER_TYPES:
        return t
    return "body"


def find_master_ph(master_el, t: str):
    want = master_type(t)
    for sp, ph in placeholders(master_el):
        if master_type(ph_type(ph)) == want:
            return sp
    return None


def xfrm(sp):
    if sp is None:
        return None
    sppr = sp.find(q("p:spPr"))
    x = None if sppr is None else sppr.find(q("a:xfrm"))
    if x is None:
        return None
    off, ext = x.find(q("a:off")), x.find(q("a:ext"))
    if off is None or ext is None:
        return None
    return int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))


def body_pr(sp):
    if sp is None:
        return None
    tx = sp.find(q("p:txBody"))
    return None if tx is None else tx.find(q("a:bodyPr"))


def lvl_ppr(container, level: int):
    """a:lvlNpPr inside an a:lstStyle or p:bodyStyle style container."""
    if container is None:
        return None
    return container.find(q("a:lvl%dpPr" % level))


def lst_style(sp):
    if sp is None:
        return None
    tx = sp.find(q("p:txBody"))
    return None if tx is None else tx.find(q("a:lstStyle"))


def spacing(ppr, tag: str, size_hpt: int):
    """Resolved spacing in EMU from an a:lnSpc / a:spcBef / a:spcAft child, or None when unset.
    Percent values are read as a share of single spacing (1.2 em), D5."""
    if ppr is None:
        return None
    el = ppr.find(q("a:" + tag))
    if el is None:
        return None
    pts = el.find(q("a:spcPts"))
    if pts is not None:
        return int(pts.get("val")) * EMU_PER_PT // 100
    pct = el.find(q("a:spcPct"))
    if pct is not None:
        val = pct.get("val", "100000")
        # Transitional files store thousandths of a percent (90000); strict files "90%".
        frac = float(val[:-1]) / 100 if val.endswith("%") else int(val) / 100000
        return int(size_hpt * EMU_PER_PT / 100 * 1.2 * frac)
    return None


def resolve_level(chain_pprs, level: int) -> Level:
    """First value found walking layout lstStyle, master lstStyle, master txStyles, defaults."""
    pprs = [lvl_ppr(c, level) for c in chain_pprs]
    size = DEF_SZ
    for ppr in pprs:
        if ppr is None:
            continue
        d = ppr.find(q("a:defRPr"))
        if d is not None and d.get("sz"):
            size = int(d.get("sz"))
            break
    margin = 0
    for ppr in pprs:
        if ppr is not None and ppr.get("marL") is not None:
            margin = int(ppr.get("marL"))
            break
    vals = {}
    for tag in ("lnSpc", "spcBef", "spcAft"):
        vals[tag] = None
        for ppr in pprs:
            v = spacing(ppr, tag, size)
            if v is not None:
                vals[tag] = v
                break
    size_emu = size * EMU_PER_PT // 100
    line = vals["lnSpc"] if vals["lnSpc"] is not None else int(size_emu * 1.2)
    return Level(size_emu, line, vals["spcBef"] or 0, vals["spcAft"] or 0, max(margin, 0))


def measure_body(sp, master_sp, style_chain) -> tuple[Fit | None, str, tuple | None]:
    box = xfrm(sp) or xfrm(master_sp)
    if box is None:
        return None, "no box", None
    attrs: dict[str, str] = {}
    autofit = None
    for bp in (body_pr(sp), body_pr(master_sp)):
        if bp is None:
            continue
        for k, v in bp.attrib.items():
            attrs.setdefault(k, v)
        if autofit is None:
            for child in bp:
                if child.tag in (q("a:noAutofit"), q("a:normAutofit"), q("a:spAutoFit")):
                    autofit = child.tag.split("}")[1]
                    break
    if attrs.get("wrap") == "none":
        return None, "wrapping off", box
    if attrs.get("vert", "horz") in UNMODELLED_VERT:
        return None, "vertical text", box
    if int(attrs.get("numCol", "1")) > 1:
        return None, "columns in box", box
    if autofit == "spAutoFit":
        return None, "shape autofit", box
    l_ins = int(attrs.get("lIns", DEF_LR_INS))
    r_ins = int(attrs.get("rIns", DEF_LR_INS))
    t_ins = int(attrs.get("tIns", DEF_TB_INS))
    b_ins = int(attrs.get("bIns", DEF_TB_INS))
    _, _, cx, cy = box
    levels = (resolve_level(style_chain, 1), resolve_level(style_chain, 2))
    return Fit(cx - l_ins - r_ins, cy - t_ins - b_ins, levels), "", box


def overlap_x(a: Body, b: Body) -> bool:
    if None in (a.x, a.cx, b.x, b.cx):
        return True
    return not (a.x + a.cx <= b.x or b.x + b.cx <= a.x)


def column_pair(bodies: tuple[Body, ...]) -> tuple[int, int] | None:
    """The two largest bodies, when they do not overlap horizontally, ordered by x."""
    if len(bodies) < 2:
        return None
    ranked = sorted(bodies, key=lambda b: (-b.area, b.x or 0))
    a, b = ranked[0], ranked[1]
    if overlap_x(a, b):
        return None
    left, right = sorted((a, b), key=lambda b_: b_.x)
    return left.idx, right.idx


def classify(layout_type: str, title_idx, subtitle_idx, ctr_title: bool, bodies, columns) -> str:
    """D3 steps 1 to 3."""
    typed = TYPED_CLASS.get(layout_type)
    if typed:
        ok = {
            "title": title_idx is not None,
            "content": title_idx is not None and len(bodies) >= 1,
            "two": title_idx is not None and columns is not None,
            "section": title_idx is not None,
        }[typed]
        if ok:
            return typed
    # step 2
    if title_idx is None:
        return "other"
    if ctr_title or (subtitle_idx is not None and not bodies):
        return "title"
    if len(bodies) == 1 and subtitle_idx is None:
        return "content"
    if len(bodies) == 2 and columns is not None and subtitle_idx is None:
        return "two"
    if not bodies and subtitle_idx is None:
        return "section"
    return "other"


def read_layout(layout, master_index: int, master_el, pres_el) -> Layout:
    el = layout._element
    title_idx = subtitle_idx = None
    ctr = False
    bodies = []
    footers = []
    master_body_style = master_el.find(q("p:txStyles"))
    body_style = None if master_body_style is None else master_body_style.find(q("p:bodyStyle"))
    default_style = pres_el.find(q("p:defaultTextStyle"))
    for sp, ph in placeholders(el):
        t = ph_type(ph)
        if t in FOOTER_TYPES:
            footers.append(t)
            continue
        if t in IGNORED_TYPES:
            continue
        if t in TITLE_TYPES:
            if title_idx is None:
                title_idx = ph_idx(ph)
                ctr = ctr or t == "ctrTitle"
            continue
        if t == "subTitle":
            if subtitle_idx is None:
                subtitle_idx = ph_idx(ph)
            continue
        if t in BODY_TYPES:
            msp = find_master_ph(master_el, t)
            chain = (lst_style(sp), lst_style(msp), body_style, default_style)
            fit, why, box = measure_body(sp, msp, chain)
            x, y, cx, cy = box if box else (None, None, None, None)
            bodies.append(Body(ph_idx(ph), x, y, cx, cy, fit, why))
    bodies_t = tuple(bodies)
    columns = column_pair(bodies_t)
    main_body = None
    if bodies_t:
        main_body = sorted(bodies_t, key=lambda b: (-b.area, b.x or 0))[0].idx
    cls = classify(el.get("type", "cust"), title_idx, subtitle_idx, ctr, bodies_t, columns)
    return Layout(
        id=str(layout.part.partname),
        name=layout.name or "",
        master=master_index,
        cls=cls,
        title_idx=title_idx,
        subtitle_idx=subtitle_idx,
        bodies=bodies_t,
        main_body=main_body,
        columns=columns,
        footers=tuple(dict.fromkeys(footers)),
    )


_cache: dict[str, tuple[TemplateInfo, Package]] = {}


def open_template(data: bytes, filename: str) -> tuple[TemplateInfo, Package]:
    """read_template plus the loaded package, cached on the bytes so the page's separate
    steps do not repeat the work."""
    key = hashlib.sha256(data).hexdigest() + "|" + filename
    hit = _cache.get(key)
    if hit:
        return hit
    pkg = load(data, filename)
    from pptx import Presentation

    try:
        prs = Presentation(io.BytesIO(pkg.zip_bytes()))
    except TemplateError:
        raise
    except Exception as e:
        raise TemplateError("bad_file", f"python-pptx: {e}") from e
    pres_el = prs.part._element
    layouts = []
    masters = []
    for mi, master in enumerate(prs.slide_masters):
        masters.append(master._element.find(q("p:cSld")).get("name", "") or "")
        for layout in master.slide_layouts:
            layouts.append(read_layout(layout, mi, master._element, pres_el))
    from .sample import read_samples, sample_default, sample_route_available

    samples = read_samples(prs)
    layout_ok = any(lay.title_idx is not None and lay.bodies for lay in layouts)
    sample_ok = sample_route_available(samples)
    if not layout_ok and not sample_ok:
        raise TemplateError("no_text_layout")
    routes = tuple(r for r, ok in (("sample", sample_ok), ("layout", layout_ok)) if ok)
    route = routes[0] if len(routes) == 1 else ("sample" if sample_default(samples) else "layout")
    defaults = []
    for cls in ("title", "content", "two", "section"):
        first = next((lay.id for lay in layouts if lay.cls == cls), None)
        defaults.append((cls, first))
    info = TemplateInfo(
        filename=filename,
        kind=pkg.kind,
        masters=tuple(masters),
        layouts=tuple(layouts),
        defaults=tuple(defaults),
        slide_count=len(prs.slides),
        samples=samples,
        routes=routes,
        route=route,
    )
    _cache.clear()
    _cache[key] = (info, pkg)
    return info, pkg


def read_template(data: bytes, filename: str) -> TemplateInfo:
    return open_template(data, filename)[0]
