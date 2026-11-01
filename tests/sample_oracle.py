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
