"""C23 comparator, written apart from deckfill: every copied slide's background and kept shapes match its source sample.

Compared per copy (the sample found by shape signature, sample_oracle.which_sample): p:bg and p:clrMapOvr; for every
shape kept from the sample, its slide-space box, its p:spPr without a:xfrm (fills, lines, geometry), its a:srcRect
crops and the SHA-256 of every picture or media target, and the z-order of kept shapes. Declared edits pass: text in
boxes, removed text boxes without fill or line, title fragments and placeholders, groups those removals emptied,
footers, shape and relationship ids, and the title widening (the joined title's box grows inside the union of the
removed fragments' boxes, its groups grow with it, and its branch is raised above the fragments')."""

from __future__ import annotations

import copy
import hashlib

from lxml import etree

from sample_oracle import A, FOOTER, P, R, nv_id, parts_of, ph_type, rels, slides, tree_of, which_sample, xml


def a(t):
    return "{%s}%s" % (A, t)


def p(t):
    return "{%s}%s" % (P, t)


SHAPES = {"sp", "pic", "grpSp", "cxnSp", "graphicFrame", "contentPart"}


def _xfrm(el):
    local = etree.QName(el).localname
    if local == "grpSp":
        pr = el.find(p("grpSpPr"))
    elif local == "graphicFrame":
        return el.find(p("xfrm"))
    else:
        pr = el.find(p("spPr"))
    return None if pr is None else pr.find(a("xfrm"))


def boxes(tree) -> dict[int, tuple]:
    """Slide-space box of every shape, composed through group transforms (the oracle's own arithmetic)."""
    out = {}

    def rec(parent, maps):
        for el in parent:
            if not isinstance(el.tag, str) or etree.QName(el).localname not in SHAPES:
                continue
            sid, _ = nv_id(el)
            x = _xfrm(el)
            if x is not None and x.find(a("off")) is not None and x.find(a("ext")) is not None:
                ox, oy = int(x.find(a("off")).get("x")), int(x.find(a("off")).get("y"))
                cx, cy = int(x.find(a("ext")).get("cx")), int(x.find(a("ext")).get("cy"))
                pts = [(ox, oy), (ox + cx, oy + cy)]
                for m in maps:
                    pts = [m(px, py) for px, py in pts]
                (x1, y1), (x2, y2) = pts
                out[sid] = (round(min(x1, x2)), round(min(y1, y2)), round(abs(x2 - x1)), round(abs(y2 - y1)))
                if etree.QName(el).localname == "grpSp":
                    co, ce = x.find(a("chOff")), x.find(a("chExt"))
                    c0x, c0y = (int(co.get("x")), int(co.get("y"))) if co is not None else (ox, oy)
                    cex, cey = (int(ce.get("cx")), int(ce.get("cy"))) if ce is not None else (cx, cy)
                    sx, sy = cx / cex if cex else 1, cy / cey if cey else 1

                    def m(px, py, ox=ox, oy=oy, c0x=c0x, c0y=c0y, sx=sx, sy=sy):
                        return ox + (px - c0x) * sx, oy + (py - c0y) * sy
                    rec(el, [m] + maps)
            elif etree.QName(el).localname == "grpSp":
                rec(el, maps)

    rec(tree, [])
    return out


def shapes(tree) -> dict[int, object]:
    out = {}

    def rec(parent):
        for el in parent:
            if isinstance(el.tag, str) and etree.QName(el).localname in SHAPES:
                out[nv_id(el)[0]] = el
                if etree.QName(el).localname == "grpSp":
                    rec(el)

    rec(tree)
    return out


def _hash_refs(el, parts, name):
    """A copy of el whose relationship ids are replaced by the SHA-256 of their targets (ids may differ; bytes may not)."""
    rs = rels(parts, name)
    el = copy.deepcopy(el)
    for e in el.iter():
        for k, v in list(e.attrib.items()):
            if k.startswith("{%s}" % R):
                rel = rs.get(v)
                if rel is None:
                    e.set(k, "missing")
                elif rel[2]:
                    e.set(k, "ext:" + rel[1])
                else:
                    e.set(k, hashlib.sha256(parts.get(rel[1], b"")).hexdigest())
    return el


def _canon(el) -> bytes:
    return b"" if el is None else etree.tostring(el, method="c14n")


def _sppr(el, parts, name):
    """The shape's own properties without its box: fills, lines, geometry, picture fill and crop."""
    local = etree.QName(el).localname
    keep = []
    pr = el.find(p("grpSpPr") if local == "grpSp" else p("spPr"))
    if pr is not None:
        c = _hash_refs(pr, parts, name)
        for x in c.findall(a("xfrm")):
            c.remove(x)
        keep.append(_canon(c))
    bf = el.find(p("blipFill"))
    if bf is not None:
        keep.append(_canon(_hash_refs(bf, parts, name)))
    return b"|".join(keep)


def _has_text(el) -> bool:
    tx = el.find(p("txBody"))
    return tx is not None and (any((t.text or "").strip() for t in tx.iter(a("t"))) or tx.find(".//" + a("fld")) is not None)


def _decorated(el) -> bool:
    pr = el.find(p("spPr"))
    if pr is None:
        return False
    if any(pr.find(a(t)) is not None for t in ("solidFill", "gradFill", "blipFill", "pattFill", "grpFill")):
        return True
    ln = pr.find(a("ln"))
    if ln is not None and ln.find(a("noFill")) is None and (len(ln) or ln.get("w")):
        return True
    st = el.find(p("style"))
    if st is not None and pr.find(a("noFill")) is None:
        fr = st.find(a("fillRef"))
        if fr is not None and fr.get("idx", "0") != "0":
            return True
    return False


def _within(inner, outer) -> bool:
    return inner[0] >= outer[0] - 2 and inner[1] >= outer[1] - 2 and inner[0] + inner[2] <= outer[0] + outer[2] + 2 and inner[1] + inner[3] <= outer[1] + outer[3] + 2


def _union(bs):
    x1, y1 = min(b[0] for b in bs), min(b[1] for b in bs)
    x2, y2 = max(b[0] + b[2] for b in bs), max(b[1] + b[3] for b in bs)
    return (x1, y1, x2 - x1, y2 - y1)


def look_diff(out: bytes, src: bytes) -> list[str]:
    op, sp = parts_of(out), parts_of(src)
    src_names = slides(sp)
    diffs: list[str] = []
    for n, name in enumerate(slides(op), start=1):
        k = which_sample(sp, op[name])
        sname = src_names[k - 1]
        o_root, s_root = xml(op[name]), xml(sp[sname])
        o_bg = o_root.find(p("cSld")).find(p("bg"))
        s_bg = s_root.find(p("cSld")).find(p("bg"))
        if (o_bg is None) != (s_bg is None) or (o_bg is not None and _canon(_hash_refs(o_bg, op, name)) != _canon(_hash_refs(s_bg, sp, sname))):
            diffs.append(f"slide {n} (s{k}): background differs")
        if _canon(o_root.find(p("clrMapOvr"))) != _canon(s_root.find(p("clrMapOvr"))):
            diffs.append(f"slide {n} (s{k}): colour map override differs")
        ot, st = tree_of(op[name]), tree_of(sp[sname])
        o_sh, s_sh = shapes(ot), shapes(st)
        o_bx, s_bx = boxes(ot), boxes(st)
        o_sh = {i: e for i, e in o_sh.items() if not (etree.QName(e).localname == "sp" and ph_type(e) in FOOTER)}
        removed = [i for i in s_sh if i not in o_sh]
        removed_text = [s_bx[i] for i in removed if i in s_bx and etree.QName(s_sh[i]).localname == "sp" and _has_text(s_sh[i])]
        for i in removed:
            el = s_sh[i]
            local = etree.QName(el).localname
            if local == "sp" and ph_type(el) in FOOTER:
                continue
            if local == "sp" and (_has_text(el) and (not _decorated(el) or ph_type(el) is not None)):
                continue  # a cleared text box, a title fragment or a placeholder
            if local == "grpSp" and all(j in removed for j in shapes(el) if j != i) and not any(
                    etree.QName(c).localname != "sp" or not _has_text(c) or _decorated(c) for c in shapes(el).values() if c is not el
                    and etree.QName(c).localname != "grpSp"):
                continue  # a group its removals emptied
            diffs.append(f"slide {n} (s{k}): shape {i} ({local}) missing")
        widened = set()
        for i, el in o_sh.items():
            if i not in s_sh:
                continue  # added shapes are footers (declared)
            if _sppr(el, op, name) != _sppr(s_sh[i], sp, sname):
                diffs.append(f"slide {n} (s{k}): shape {i} properties differ (fill, line, geometry, crop or media)")
            if o_bx.get(i) != s_bx.get(i):
                ob, sb = o_bx.get(i), s_bx.get(i)
                if ob and sb and _within(sb, ob) and removed_text and _within(ob, _union([sb] + removed_text)):
                    widened.add(i)  # the declared title widening (or a group grown with it)
                else:
                    diffs.append(f"slide {n} (s{k}): shape {i} box {sb} -> {ob}")

        def order(tree, keep):
            seq = []
            for el in tree:
                if isinstance(el.tag, str) and etree.QName(el).localname in SHAPES:
                    i = nv_id(el)[0]
                    if i in keep:
                        seq.append(i)
            return seq

        # z-order of kept shapes in every container, the widened title's branch set aside
        for cid, cont in [(None, st)] + [(i, e) for i, e in s_sh.items() if etree.QName(e).localname == "grpSp"]:
            oc = ot if cid is None else o_sh.get(cid)
            if oc is None:
                continue
            keep = {i for i in o_sh if i in s_sh and i not in widened}
            if order(oc, keep) != order(cont, keep):
                diffs.append(f"slide {n} (s{k}): z-order differs in {'the slide' if cid is None else 'group ' + str(cid)}")
    return diffs
