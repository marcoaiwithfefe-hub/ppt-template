"""Test-side readers of an output deck, written apart from deckfill so the checks do not share
its code paths: what text sits where (C1), which parts were kept (C3), placeholders (C4, C6)."""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from urllib.parse import unquote

from lxml import etree

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
RT_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
RT_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
RT_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
TITLE = {"title", "ctrTitle"}
BODY = {"body", "obj"}
FOOTER = {"sldNum", "ftr", "dt"}
_PARSER = dict(remove_blank_text=True, resolve_entities=False, no_network=True)


def a(tag):
    return "{%s}%s" % (A, tag)


def p(tag):
    return "{%s}%s" % (P, tag)


def parts_of(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def xml(data: bytes):
    return etree.fromstring(data, etree.XMLParser(**_PARSER))


def rels_of(parts, name):
    d, f = posixpath.split(name)
    rn = posixpath.join(d, "_rels", f + ".rels") if name else "_rels/.rels"
    out = {}
    if rn not in parts:
        return out
    for e in xml(parts[rn]):
        t = e.get("Target")
        ext = e.get("TargetMode") == "External"
        if not ext:
            t = unquote(t)
            t = t[1:] if t.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(name), t))
        out[e.get("Id")] = (e.get("Type"), t, ext)
    return out


def para_text(pel) -> str:
    return "".join((t.text or "") for t in pel.iter(a("t")))


def ph_info(sp):
    ph = sp.find(p("nvSpPr") + "/" + p("nvPr") + "/" + p("ph"))
    if ph is None:
        return None
    return ph.get("type", "obj"), int(ph.get("idx", "0"))


def xfrm_x(sp):
    off = sp.find(p("spPr") + "/" + a("xfrm") + "/" + a("off"))
    return None if off is None else int(off.get("x"))


@dataclass
class OutSlide:
    n: int
    layout: str
    layout_name: str
    title: str | None = None
    subtitle: list[str] = field(default_factory=list)
    bodies: list[list[tuple[int, str]]] = field(default_factory=list)  # left to right
    placeholders: list[tuple[str, int, bool]] = field(default_factory=list)  # type, idx, has text
    footers: dict = field(default_factory=dict)  # type -> sp element
    run_props: list = field(default_factory=list)  # a:rPr elements on runs
    loose_text: list[str] = field(default_factory=list)  # text in any shape that is not a placeholder (F12)


def slide_order(parts) -> list[str]:
    main = next(t for (ty, t, _) in rels_of(parts, "").values() if ty.endswith("/officeDocument"))
    prels = rels_of(parts, main)
    pres = xml(parts[main])
    return [prels[s.get("{%s}id" % R)][1] for s in pres.iter(p("sldId"))]


def layout_x(parts, layout_name, master_name, ptype, idx):
    """x of a placeholder from the layout, else the master's placeholder of the same kind."""
    lay = xml(parts[layout_name])
    for sp in lay.iter(p("sp")):
        info = ph_info(sp)
        if info and info[1] == idx and info[0] == ptype:
            x = xfrm_x(sp)
            if x is not None:
                return x
    want = "title" if ptype in TITLE else ptype if ptype in FOOTER else "body"
    for sp in xml(parts[master_name]).iter(p("sp")):
        info = ph_info(sp)
        if info:
            kind = "title" if info[0] in TITLE else info[0] if info[0] in FOOTER else "body"
            if kind == want and xfrm_x(sp) is not None:
                return xfrm_x(sp)
    return 0


def read_deck(data: bytes) -> list[OutSlide]:
    parts = parts_of(data)
    out = []
    for n, name in enumerate(slide_order(parts), 1):
        srels = rels_of(parts, name)
        layout = next(t for (ty, t, _) in srels.values() if ty == RT_LAYOUT)
        master = next(t for (ty, t, _) in rels_of(parts, layout).values() if ty == RT_MASTER)
        lname = xml(parts[layout]).find(p("cSld")).get("name", "")
        s = OutSlide(n, layout, lname)
        root = xml(parts[name])
        bodies = []
        for sp in root.find(p("cSld")).find(p("spTree")):
            info = ph_info(sp) if sp.tag == p("sp") else None
            if sp.tag == p("sp"):
                for r in sp.iter(a("r")):
                    rp = r.find(a("rPr"))
                    s.run_props.append(rp)
            if not info:
                continue
            ptype, idx = info
            paras = sp.findall(".//" + a("p"))
            has_text = any(para_text(x).strip() for x in paras)
            s.placeholders.append((ptype, idx, has_text))
            if ptype in FOOTER:
                s.footers[ptype] = sp
            elif ptype in TITLE:
                s.title = "".join(para_text(x) for x in paras)
            elif ptype == "subTitle":
                s.subtitle = [para_text(x) for x in paras]
            elif ptype in BODY:
                items = []
                for x in paras:
                    ppr = x.find(a("pPr"))
                    lvl = int(ppr.get("lvl", "0")) if ppr is not None else 0
                    items.append((lvl + 1, para_text(x)))
                bodies.append((layout_x(parts, layout, master, ptype, idx), idx, items))
        s.bodies = [items for _, _, items in sorted(bodies, key=lambda b: (b[0], b[1]))]
        s.loose_text = loose_text(root)
        out.append(s)
    return out


def loose_text(slide_root) -> list[str]:
    """Every non-empty text run on a slide whose shape is not a placeholder: text boxes, shapes,
    tables and anything inside a group (Codex round 1, F12)."""
    found = []
    for t in slide_root.iter(a("t")):
        if not (t.text or "").strip():
            continue
        el, in_placeholder = t.getparent(), False
        while el is not None:
            if el.tag == p("sp"):
                in_placeholder = ph_info(el) is not None
                break
            if el.tag == p("graphicFrame"):
                break
            el = el.getparent()
        if not in_placeholder:
            found.append(t.text)
    return found


def deck_lines(deck: list[OutSlide]) -> list[str]:
    """The golden-file view of a deck: one line per content item, in order."""
    lines = []
    for s in deck:
        if s.title:
            lines.append(f"slide {s.n} title {s.title}")
        for t in s.subtitle:
            if t:
                lines.append(f"slide {s.n} subtitle {t}")
        for ci, items in enumerate(s.bodies, 1):
            for lvl, text in items:
                lines.append(f"slide {s.n} body{ci} L{lvl} {text}")
    return lines


def read_golden(path) -> tuple[list[str], list[str], list[str]]:
    """Content lines, parser warnings ('warn <line> <code>'), plan warnings ('planwarn ...')."""
    content, warns, planwarns = [], [], []
    for raw in open(path, encoding="utf-8").read().splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#!"):
            continue
        if line.startswith("warn "):
            warns.append(line)
        elif line.startswith("planwarn "):
            planwarns.append(line)
        else:
            content.append(line)
    return content, warns, planwarns


# ---------------------------------------------------------------------------------------------
# C3: kept parts


def canonical(data: bytes) -> str:
    root = xml(data)
    return etree.tostring(root, method="c14n2").decode()


def reachable(parts, skip_targets=frozenset(), skip_rels=frozenset()):
    """Member names reachable from the package root. skip_targets: parts not entered.
    skip_rels: (source, rId) pairs not followed."""
    seen, stack = set(), [""]
    while stack:
        src = stack.pop()
        for rid, (ty, t, ext) in rels_of(parts, src).items():
            if ext or (src, rid) in skip_rels or t in skip_targets or t in seen or t not in parts:
                continue
            seen.add(t)
            stack.append(t)
    return seen


def removed_slide_links(parts):
    """Slides of the input, and every (source, rId) relationship that points at one."""
    slides = set(slide_order(parts))
    links = set()
    for src in reachable(parts) | {""}:
        for rid, (ty, t, ext) in rels_of(parts, src).items():
            if not ext and t in slides:
                links.add((src, rid))
    return slides, links


def is_rels(name):
    return name.endswith(".rels")


def content_type(parts, name) -> str:
    ct = xml(parts["[Content_Types].xml"])
    for e in ct:
        if e.get("PartName", "").lstrip("/") == name:
            return e.get("ContentType", "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in posixpath.basename(name) else ""
    for e in ct:
        if (e.get("Extension") or "").lower() == ext:
            return e.get("ContentType", "")
    return ""


def is_xml_part(parts, name) -> bool:
    ct = content_type(parts, name)
    return name.endswith(".xml") or ct.endswith("+xml") or ct in ("application/xml", "text/xml")


def without_links(data: bytes, dead: set) -> str:
    """Canonical XML of a part with only the authorised edit made: every element that uses one of
    the removed-slide relationships taken out (D4), nothing else."""
    root = xml(data)
    for el in list(root.iter()):
        if any(k.startswith("{%s}" % R) and v in dead for k, v in el.attrib.items()):
            el.getparent().remove(el)
    return etree.tostring(root, method="c14n2").decode()


def rel_set(parts, name, dead=frozenset()):
    return {(rid, ty, t, ext) for rid, (ty, t, ext) in rels_of(parts, name).items() if rid not in dead}


def kept_part_problems(inp: bytes, out: bytes, allowed_extra_changes=()) -> list[str]:
    """Every input part outside D4's allowed changes is in the output: binary parts byte for byte,
    XML parts equal after canonicalisation. A part that linked to a removed slide is compared after
    taking out only those link elements and relationships (Codex round 1, F11), so any other
    change to it still counts."""
    ip, op = parts_of(inp), parts_of(out)
    slides, links = removed_slide_links(ip)
    kept = reachable(ip, skip_targets=slides)
    main = next(t for (ty, t, _) in rels_of(ip, "").values() if ty.endswith("/officeDocument"))
    allowed = {main, "[Content_Types].xml", "docProps/app.xml"} | set(allowed_extra_changes)
    problems = []
    for name in sorted(kept):
        if name in allowed:
            continue
        if name not in op:
            problems.append(f"missing {name}")
            continue
        dead = {rid for (src, rid) in links if src == name}
        if is_xml_part(ip, name):
            if without_links(ip[name], dead) != canonical(op[name]):
                problems.append(f"changed {name}")
        elif ip[name] != op[name]:
            problems.append(f"bytes changed {name}")
        # its relationships too, except the ones to removed slides
        if rel_set(ip, name, dead) != rel_set(op, name):
            problems.append(f"changed relationships of {name}")
    return problems


def new_parts(inp: bytes, out: bytes) -> list[str]:
    ip, op = parts_of(inp), parts_of(out)
    return sorted(n for n in op if n not in ip)
