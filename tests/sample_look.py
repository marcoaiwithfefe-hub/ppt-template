"""C23 comparator, written apart from deckfill: every copied slide's background and kept shapes match its source sample.

Compared per copy (the sample found by shape signature, sample_oracle.which_sample): p:bg and p:clrMapOvr; for every
shape kept from the sample, its slide-space box, its p:spPr without a:xfrm (fills, lines, geometry), its a:srcRect
crops and the SHA-256 of every picture or media target, and the z-order of kept shapes. Declared edits pass: text in
boxes, removed text boxes without fill or line, title fragments and placeholders, QA round 1's chips and backings
(computed here from the source sample by the Q1 rule, see allowed_removals), groups those removals emptied, footers,
shape and relationship ids, and the title widening (the joined title's box grows inside the union of the removed
fragments' boxes, its groups grow with it, and its branch is raised above the fragments')."""

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


def _share_inside(inner, outer) -> float:
    ix = min(inner[0] + inner[2], outer[0] + outer[2]) - max(inner[0], outer[0])
    iy = min(inner[1] + inner[3], outer[1] + outer[3]) - max(inner[1], outer[1])
    area = inner[2] * inner[3]
    return ix * iy / area if ix > 0 and iy > 0 and area > 0 else 0.0


def _hidden_ids(tree) -> set[int]:
    """Shapes hidden by their own cNvPr or an enclosing group's."""
    out: set[int] = set()

    def rec(parent, hidden):
        for el in parent:
            if not isinstance(el.tag, str) or etree.QName(el).localname not in SHAPES:
                continue
            nv = next((c for c in el if etree.QName(c).localname.startswith("nv")), None)
            c = None if nv is None else nv.find(p("cNvPr"))
            h = hidden or (c is not None and c.get("hidden") in ("1", "true"))
            if h:
                out.add(nv_id(el)[0])
            if etree.QName(el).localname == "grpSp":
                rec(el, h)

    rec(tree, False)
    return out


def _slide_area(parts) -> int:
    sz = xml(parts["ppt/presentation.xml"]).find(p("sldSz"))
    return int(sz.get("cx")) * int(sz.get("cy"))


def allowed_removals(s_sh, s_bx, o_sh, o_bx, hidden, area) -> set[int]:
    """QA round 1 (Q1, C23 amended): the shapes a copy may lose, computed from the source sample and the output's
    destinations, never from the fill's record. Footers; text boxes with no fill or line, and placeholders; a text
    shape with a fill or line under 8% of the slide; a text-free shape with a fill or line under 8% that holds at least
    80% of a cleared text box (its backing); a group whose visible members are all gone, with its hidden members.
    Nothing that holds 80% of a destination's output box may go, and neither may anything 8% or larger."""
    dests = {i for i, el in o_sh.items() if i in s_sh and etree.QName(el).localname == "sp" and _has_text(el)}
    dest_boxes = [o_bx[i] for i in dests if i in o_bx]
    cleared = [s_bx[i] for i, el in s_sh.items() if etree.QName(el).localname == "sp" and _has_text(el) and i not in dests
               and i not in hidden and ph_type(el) not in FOOTER and i in s_bx]
    removed = {i for i in s_sh if i not in o_sh}

    def small_free(i) -> bool:
        b = s_bx.get(i)
        return b is not None and b[2] * b[3] < 0.08 * area and not any(_share_inside(d, b) >= 0.8 for d in dest_boxes)

    ok: set[int] = set()
    for i in removed:
        el = s_sh[i]
        local = etree.QName(el).localname
        if local != "sp":
            continue
        if ph_type(el) in FOOTER:
            ok.add(i)
        elif _has_text(el):
            if not _decorated(el) or ph_type(el) is not None or small_free(i):
                ok.add(i)
        elif ph_type(el) is None and _decorated(el) and small_free(i) and any(_share_inside(c, s_bx[i]) >= 0.8 for c in cleared):
            ok.add(i)
    # groups, innermost first: every visible member gone with an allowed reason; hidden members go with the group
    groups = [i for i in s_sh if etree.QName(s_sh[i]).localname == "grpSp" and i in removed]
    changed = True
    while changed:
        changed = False
        for i in groups:
            if i in ok:
                continue
            members = [nv_id(c)[0] for c in s_sh[i].iter() if c is not s_sh[i] and isinstance(c.tag, str)
                       and etree.QName(c).localname in SHAPES]
            if all(j in ok or (j in hidden and j in removed) for j in members):
                ok.add(i)
                ok.update(j for j in members if j in hidden)
                changed = True
    return ok


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
        allowed = allowed_removals(s_sh, s_bx, o_sh, o_bx, _hidden_ids(st), _slide_area(sp))
        for i in removed:
            if i not in allowed:
                diffs.append(f"slide {n} (s{k}): shape {i} ({etree.QName(s_sh[i]).localname}) missing")
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
