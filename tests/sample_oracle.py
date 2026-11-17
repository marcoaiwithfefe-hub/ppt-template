"""Test-side readers of sample-route outputs (C23, C24, C27), written apart from deckfill: no import from deckfill.

text_lines: every output slide's text, walked recursively through groups and hidden shapes, fields included, by source
shape id, with the sample slide each copy came from (found by shape signature against the template), and the footers.
The goldens in tests/goldens/sample/ use the same line format and are written by hand from spec D12."""

from __future__ import annotations

import io
import posixpath
import zipfile
from urllib.parse import unquote

from lxml import etree

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
FOOTER = {"sldNum", "ftr", "dt"}
SHAPES = {"sp", "pic", "grpSp", "cxnSp", "graphicFrame", "contentPart"}
_PARSER = dict(remove_blank_text=True, resolve_entities=False, no_network=True)


def a(t):
    return "{%s}%s" % (A, t)


def p(t):
    return "{%s}%s" % (P, t)


def parts_of(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def xml(b: bytes):
    return etree.fromstring(b, etree.XMLParser(**_PARSER))


def rels(parts, name):
    d, f = posixpath.split(name)
    rn = posixpath.join(d, "_rels", f + ".rels")
    out = {}
    if rn in parts:
        for e in xml(parts[rn]):
            t = e.get("Target")
            ext = e.get("TargetMode") == "External"
            if not ext:
                t = unquote(t)
                t = t[1:] if t.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(name), t))
            out[e.get("Id")] = (e.get("Type"), t, ext)
    return out


def slides(parts) -> list[str]:
    """Slide part names in presentation order."""
    main = "ppt/presentation.xml"
    rs = rels(parts, main)
    return [rs[s.get("{%s}id" % R)][1] for s in xml(parts[main]).iter(p("sldId"))]


def walk(el):
    """Every shape element under a shape tree or group, in document order, groups included."""
    for c in el:
        if not isinstance(c.tag, str):
            continue
        local = etree.QName(c).localname
        if local == "AlternateContent":
            fb = [x for x in c if isinstance(x.tag, str) and etree.QName(x).localname == "Fallback"]
            for f in fb:
                yield from walk(f)
            continue
        if local in SHAPES:
            yield c
            if local == "grpSp":
                yield from walk(c)


def nv_id(el):
    for c in el:
        if isinstance(c.tag, str) and etree.QName(c).localname.startswith("nv"):
            pr = c.find(p("cNvPr"))
            if pr is not None:
                return int(pr.get("id")), pr.get("name", "")
    return None, ""


def ph_type(el):
    nv = el.find(p("nvSpPr"))
    ph = None if nv is None else nv.find(p("nvPr")).find(p("ph"))
    return None if ph is None else ph.get("type", "obj")


def para_text(par) -> str:
    out = []
    for c in par:
        if c.tag in (a("r"), a("fld")):
            t = c.find(a("t"))
            out.append(t.text or "" if t is not None else "")
        elif c.tag == a("br"):
            out.append("\n")
    return "".join(out)


def tree_of(slide_xml: bytes):
    return xml(slide_xml).find(p("cSld")).find(p("spTree"))


def signature(slide_xml: bytes) -> set:
    """Shape ids and names of every non-footer shape: how a copy is matched to its sample."""
    out = set()
    for el in walk(tree_of(slide_xml)):
        if etree.QName(el).localname == "sp" and ph_type(el) in FOOTER:
            continue
        out.add(nv_id(el))
    return out


def which_sample(src_parts, out_xml: bytes) -> int:
    sig = signature(out_xml)
    best, best_k = -1.0, 0
    for k, name in enumerate(slides(src_parts), start=1):
        s = signature(src_parts[name])
        score = len(sig & s) / max(len(sig), 1) - 0.001 * len(s - sig) / max(len(s), 1)
        if score > best:
            best, best_k = score, k
    return best_k


def text_lines(out: bytes, src: bytes) -> list[str]:
    """The golden line format: 'slide n sK', then 'sid level text' per paragraph with text, then 'footer type text'."""
    op, sp = parts_of(out), parts_of(src)
    lines = []
    for n, name in enumerate(slides(op), start=1):
        x = op[name]
        lines.append(f"slide {n} s{which_sample(sp, x)}")
        foot = []
        for el in walk(tree_of(x)):
            if etree.QName(el).localname != "sp":
                continue
            tx = el.find(p("txBody"))
            if tx is None:
                continue
            sid, _ = nv_id(el)
            t = ph_type(el)
            for par in tx.findall(a("p")):
                text = para_text(par)
                if not text.strip():
                    continue
                if t in FOOTER:
                    foot.append(f"footer {t} {text}")
                    continue
                ppr = par.find(a("pPr"))
                lvl = int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1
                lines.append(f"{sid} {lvl} {text}")
        lines += foot
        # code review F1: text inside an mc:Choice branch is text PowerPoint can draw instead of the fallback; it is
        # listed so any that survives fails the golden comparison (C24)
        for ch in xml(x).iter():
            if isinstance(ch.tag, str) and etree.QName(ch).localname == "Choice":
                lines += [f"choice {t.text}" for t in ch.iter(a("t")) if (t.text or "").strip()]
    return lines


def golden(path) -> list[str]:
    return [ln.rstrip("\n") for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]


# ---------------------------------------------------------------------------------------------------------------------
# resolved paragraph properties (C25, code review F6): the spec's D12 inheritance walked on the output package itself

TITLE_PH = {"title", "ctrTitle"}
FOOTER_PH = {"dt", "ftr", "sldNum"}


def _ph(el):
    nv = el.find(p("nvSpPr"))
    nvpr = None if nv is None else nv.find(p("nvPr"))
    ph = None if nvpr is None else nvpr.find(p("ph"))
    return None if ph is None else (ph.get("type", "obj"), ph.get("idx"))


def _phs(root):
    return [(el, _ph(el)) for el in root.iter(p("sp")) if _ph(el) is not None]


def _lvl_of(container, n):
    return None if container is None else container.find(a(f"lvl{n}pPr"))


def _lst_of(sp):
    tx = None if sp is None else sp.find(p("txBody"))
    return None if tx is None else tx.find(a("lstStyle"))


def _rel_target(parts, name, kind):
    return next(t for typ, t, _ in rels(parts, name).values() if typ.endswith("/" + kind))


def level_chain(parts, slide_name, sp, n):
    """The a:lvlNpPr elements a box's level-n paragraphs inherit, its own list style first: for a placeholder the
    layout's placeholder (same idx, else same type), the master's placeholder of its kind and the master's title or body
    text style; for a free shape the presentation's default text style (spec D12)."""
    own = [_lvl_of(_lst_of(sp), n)]
    ph = _ph(sp)
    if ph is None:
        return own + [_lvl_of(xml(parts["ppt/presentation.xml"]).find(p("defaultTextStyle")), n)]
    lay_name = _rel_target(parts, slide_name, "slideLayout")
    lay, mas = xml(parts[lay_name]), xml(parts[_rel_target(parts, lay_name, "slideMaster")])
    t, idx = ph
    lay_sp = None
    if idx is not None:
        lay_sp = next((e for e, (_, i) in _phs(lay) if i == idx), None)
    if lay_sp is None:
        lay_sp = next((e for e, (lt, _) in _phs(lay) if lt == t), None)

    def kind(x):
        return "title" if x in TITLE_PH else (x if x in FOOTER_PH else "body")

    mas_sp = next((e for e, (mt, _) in _phs(mas) if kind(mt) == kind(t)), None)
    styles = mas.find(p("txStyles"))
    style = None if styles is None else styles.find(p("titleStyle") if t in TITLE_PH else p("bodyStyle"))
    return own + [_lvl_of(_lst_of(lay_sp), n), _lvl_of(_lst_of(mas_sp), n), _lvl_of(style, n)]


def _spacing_of(chain, tag):
    for e in chain:
        el = None if e is None else e.find(a(tag))
        if el is None:
            continue
        pts, pct = el.find(a("spcPts")), el.find(a("spcPct"))
        if pts is not None:
            return ("pts", int(pts.get("val")) * 12700 / 100)
        if pct is not None:
            v = pct.get("val", "100000")
            return ("pct", float(v[:-1]) / 100 if v.endswith("%") else int(v) / 100000)
    return ("", 0.0)


def resolved_paras(parts, slide_name, sp):
    """Per paragraph with text: (level, effective size of its first run, line spacing, spacing before, spacing after,
    left margin), each walked from the run and paragraph up the box's inheritance; 18 pt when nothing sets a size."""
    out = []
    tx = sp.find(p("txBody"))
    for par in ([] if tx is None else tx.findall(a("p"))):
        if not para_text(par).strip():
            continue
        ppr = par.find(a("pPr"))
        n = int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1
        chain = [ppr] + level_chain(parts, slide_name, sp, n)
        run = next((c for c in par if c.tag in (a("r"), a("fld"))), None)
        rpr = None if run is None else run.find(a("rPr"))
        size = int(rpr.get("sz")) if rpr is not None and rpr.get("sz") else None
        for e in chain:
            d = None if e is None or size is not None else e.find(a("defRPr"))
            if d is not None and d.get("sz"):
                size = int(d.get("sz"))
        marl = next((int(e.get("marL")) for e in chain if e is not None and e.get("marL") is not None), 0)
        out.append((n, size or 1800, _spacing_of(chain, "lnSpc"), _spacing_of(chain, "spcBef"), _spacing_of(chain, "spcAft"),
                    max(marl, 0)))
    return out
