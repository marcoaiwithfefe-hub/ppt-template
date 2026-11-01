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
    """Exclusive C14N, so an element compares alone, without the namespace declarations of the part it sits in."""
    return b"" if el is None else etree.tostring(el, method="c14n", exclusive=True)


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


# --- QA round 2: R5 backings and the R3 grown body, checked here with this file's own arithmetic

RECT = {"rect", "roundRect", "snip1Rect", "snip2SameRect", "round1Rect", "round2SameRect", "flowChartProcess",
        "flowChartAlternateProcess"}


def _rect_path(pr) -> bool:
    pg = pr.find(a("prstGeom"))
    if pg is not None:
        return pg.get("prst") in RECT
    cg = pr.find(a("custGeom"))
    paths = [] if cg is None or cg.find(a("pathLst")) is None else cg.find(a("pathLst")).findall(a("path"))
    if len(paths) != 1:
        return False
    cmds = [c for c in paths[0] if isinstance(c.tag, str)]
    names = [etree.QName(c).localname for c in cmds]
    closed = bool(names) and names[-1] == "close"
    pts = [(int(c.find(a("pt")).get("x")), int(c.find(a("pt")).get("y"))) for c in cmds if etree.QName(c).localname in ("moveTo", "lnTo")]
    body = [n for n in names if n != "close"]
    if body[:1] != ["moveTo"] or any(n != "lnTo" for n in body[1:]) or len(body) not in (4, 5) or names.count("close") > 1:
        return False
    if len(pts) == 5:
        if pts[0] != pts[4]:
            return False
        pts = pts[:4]
    elif not closed:
        return False
    corners = {(x, y) for x in {q[0] for q in pts} for y in {q[1] for q in pts}}
    return len(corners) == 4 and set(pts) == corners and all(
        u[0] == v[0] or u[1] == v[1] for u, v in zip(pts, pts[1:] + pts[:1]))


def _turned_ids(tree) -> set[int]:
    """Shapes rotated or flipped, by their own a:xfrm or an enclosing group's."""
    out: set[int] = set()

    def rec(parent, turned):
        for el in parent:
            if not isinstance(el.tag, str) or etree.QName(el).localname not in SHAPES:
                continue
            x = _xfrm(el)
            t = turned or (x is not None and ((int(x.get("rot", "0") or 0) % 21600000) != 0 or x.get("flipH") in ("1", "true")
                                               or x.get("flipV") in ("1", "true")))
            if t:
                out.add(nv_id(el)[0])
            if etree.QName(el).localname == "grpSp":
                rec(el, t)

    rec(tree, False)
    return out


def _backing_ok(el, turned: bool) -> bool:
    """R5: a rectangle (preset or a four-corner path), unrotated, with a solid fill or no fill and a line."""
    pr = el.find(p("spPr"))
    if turned or pr is None or not _rect_path(pr):
        return False
    if pr.find(a("solidFill")) is not None:
        return True
    ln = pr.find(a("ln"))
    return pr.find(a("noFill")) is not None and ln is not None and ln.find(a("noFill")) is None and (len(ln) or ln.get("w"))


def _occ(tree) -> dict[int, tuple]:
    """Drawn bounds of every non-group shape, rotation and groups included (axis-aligned)."""
    import math
    out = {}

    def rot(pts, c, r):
        if not r % 21600000:
            return pts
        t = math.radians(r / 60000)
        return [(c[0] + (x - c[0]) * math.cos(t) - (y - c[1]) * math.sin(t), c[1] + (x - c[0]) * math.sin(t) + (y - c[1]) * math.cos(t)) for x, y in pts]

    def rec(parent, maps):
        for el in parent:
            if not isinstance(el.tag, str) or etree.QName(el).localname not in SHAPES:
                continue
            x = _xfrm(el)
            if x is None or x.find(a("off")) is None or x.find(a("ext")) is None:
                continue
            ox, oy = int(x.find(a("off")).get("x")), int(x.find(a("off")).get("y"))
            cx, cy = int(x.find(a("ext")).get("cx")), int(x.find(a("ext")).get("cy"))
            r = int(x.get("rot", "0") or 0)
            if etree.QName(el).localname == "grpSp":
                co, ce = x.find(a("chOff")), x.find(a("chExt"))
                c0x, c0y = (int(co.get("x")), int(co.get("y"))) if co is not None else (ox, oy)
                cex, cey = (int(ce.get("cx")), int(ce.get("cy"))) if ce is not None else (cx, cy)

                fh, fv = x.get("flipH") in ("1", "true"), x.get("flipV") in ("1", "true")

                def m(pts, ox=ox, oy=oy, c0x=c0x, c0y=c0y, sx=(cx / cex if cex else 1), sy=(cy / cey if cey else 1), r=r, cx=cx, cy=cy,
                      fh=fh, fv=fv):
                    pts = [(ox + (px - c0x) * sx, oy + (py - c0y) * sy) for px, py in pts]
                    # code review F3: a flipped group mirrors its children about its centre before it rotates
                    pts = [(2 * ox + cx - px if fh else px, 2 * oy + cy - py if fv else py) for px, py in pts]
                    return rot(pts, (ox + cx / 2, oy + cy / 2), r)
                rec(el, [m] + maps)
                continue
            pts = rot([(ox, oy), (ox + cx, oy), (ox, oy + cy), (ox + cx, oy + cy)], (ox + cx / 2, oy + cy / 2), r)
            for f in maps:
                pts = f(pts)
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            out[nv_id(el)[0]] = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    rec(tree, [])
    return out


def _fixed_parts(parts, name, root):
    """Visible non-placeholder shape bounds of the slide's layout and master, honouring showMasterSp."""
    out = []
    if root.get("showMasterSp") in ("0", "false"):
        return out
    lay = next((t for (rt, t, ext) in rels(parts, name).values() if rt.endswith("/slideLayout")), None)
    if lay is None:
        return out
    trees = [(lay, xml(parts[lay]))]
    if trees[0][1].get("showMasterSp") not in ("0", "false"):
        mas = next((t for (rt, t, ext) in rels(parts, lay).values() if rt.endswith("/slideMaster")), None)
        if mas is not None:
            trees.append((mas, xml(parts[mas])))
    for _, r in trees:
        t = r.find(p("cSld")).find(p("spTree"))
        hidden = _hidden_ids(t)
        occ = _occ(t)
        for i, el in shapes(t).items():
            if etree.QName(el).localname == "grpSp" or i in hidden or i not in occ:
                continue
            nvpr = next((c for c in el if etree.QName(c).localname.startswith("nv")), None)
            if nvpr is not None and nvpr.find(p("nvPr")) is not None and nvpr.find(p("nvPr")).find(p("ph")) is not None:
                continue
            out.append(occ[i])
    return out


def free_cells_ok(foot, ot, oroot, op, name, skip: set, sw: int, sh: int) -> bool:
    """R3 grid, recomputed: every cell the footprint overlaps by more than 1% of a cell is free of the copy's visible
    shapes (backgrounds of 60% or more aside), the 2%-padded text destinations, the layout's and master's shapes, and
    the 4% edge band."""
    W, H = 64, 36
    taken = [[False] * W for _ in range(H)]

    def mark(b):
        if b is None or b[2] * b[3] >= 0.6 * sw * sh:
            return
        for r in range(H):
            y0, y1 = r * sh / H, (r + 1) * sh / H
            if not (b[1] < y1 and b[1] + max(b[3], 1) > y0):
                continue
            for c in range(W):
                x0, x1 = c * sw / W, (c + 1) * sw / W
                if b[0] < x1 and b[0] + max(b[2], 1) > x0:
                    taken[r][c] = True

    hidden = _hidden_ids(ot)
    occ = _occ(ot)
    sh_all = shapes(ot)
    for i, el in sh_all.items():
        if etree.QName(el).localname == "grpSp" or i in hidden or i in skip or i not in occ:
            continue
        mark(occ[i])
        if etree.QName(el).localname == "sp" and _has_text(el) and ph_type(el) not in FOOTER:
            pad = 0.02 * sw
            b = occ[i]
            mark((b[0] - pad, b[1] - pad, b[2] + 2 * pad, b[3] + 2 * pad))
    for b in _fixed_parts(op, name, oroot):
        mark(b)
    for r in range(H):
        for c in range(W):
            if c / W < 0.04 or (c + 1) / W > 0.96 or r / H < 0.04 or (r + 1) / H > 0.96:
                taken[r][c] = True
    cw, ch = sw / W, sh / H
    for r in range(H):
        for c in range(W):
            ix = min(foot[0] + foot[2], (c + 1) * cw) - max(foot[0], c * cw)
            iy = min(foot[1] + foot[3], (r + 1) * ch) - max(foot[1], r * ch)
            if ix > 0 and iy > 0 and ix * iy > 0.01 * cw * ch and taken[r][c]:
                return False
    return True


def allowed_removals(s_sh, s_bx, o_sh, o_bx, hidden, area, turned=frozenset(), grown=frozenset()) -> set[int]:
    """QA round 1 (Q1, C23 amended): the shapes a copy may lose, computed from the source sample and the output's
    destinations, never from the fill's record. Footers; text boxes with no fill or line, and placeholders; a text
    shape with a fill or line under 8% of the slide; a text-free shape with a fill or line under 8% that holds at least
    80% of a cleared text box (its backing); a group whose visible members are all gone, with its hidden members.
    Nothing behind a destination that kept its text may go (it holds 80% of the destination's output box, or 80% of it
    lies inside that box), and neither may anything 8% or larger."""
    dests = {i for i, el in o_sh.items() if i in s_sh and etree.QName(el).localname == "sp" and _has_text(el)}
    dest_boxes = [s_bx[i] if i in grown else o_bx[i] for i in dests if i in o_bx]  # a grown body (R3) at its source box
    cleared = [s_bx[i] for i, el in s_sh.items() if etree.QName(el).localname == "sp" and _has_text(el) and i not in dests
               and i not in hidden and ph_type(el) not in FOOTER and i in s_bx]
    removed = {i for i in s_sh if i not in o_sh}

    def small_free(i) -> bool:
        b = s_bx.get(i)
        return b is not None and b[2] * b[3] < 0.08 * area and not any(
            _share_inside(d, b) >= 0.8 or _share_inside(b, d) >= 0.8 for d in dest_boxes)

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
        elif (ph_type(el) is None and _decorated(el) and _backing_ok(el, i in turned) and small_free(i)
              and any(_share_inside(c, s_bx[i]) >= 0.8 for c in cleared)):
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
        widened = set()
        # R3: a grown body is a text destination whose box grew past the removed text (so not the title widening);
        # its own backing is a text-free shape whose margins around it are unchanged; its enclosing groups may grow
        changed = [i for i in o_sh if i in s_sh and o_bx.get(i) != s_bx.get(i) and o_bx.get(i) and s_bx.get(i)]
        grown = [i for i in changed if etree.QName(o_sh[i]).localname == "sp" and _has_text(o_sh[i])
                 and _within(s_bx[i], o_bx[i]) and not (removed_text and _within(o_bx[i], _union([s_bx[i]] + removed_text)))]
        backing = None
        if len(grown) == 1:
            g = grown[0]

            def margins(bx, j):
                return (bx[g][0] - bx[j][0], bx[g][1] - bx[j][1], bx[j][0] + bx[j][2] - bx[g][0] - bx[g][2],
                        bx[j][1] + bx[j][3] - bx[g][1] - bx[g][3])
            backs = [j for j in changed if j != g and etree.QName(o_sh[j]).localname == "sp" and not _has_text(o_sh[j])
                     and all(abs(u - v) <= 12 for u, v in zip(margins(o_bx, j), margins(s_bx, j)))]
            backing = backs[0] if len(backs) == 1 else None
            foot = _union([o_bx[g]] + ([o_bx[backing]] if backing is not None else []))
            sz = xml(sp["ppt/presentation.xml"]).find(p("sldSz"))
            if not free_cells_ok(foot, ot, o_root, op, name, {g} | ({backing} if backing is not None else set()),
                                 int(sz.get("cx")), int(sz.get("cy"))):
                diffs.append(f"slide {n} (s{k}): grown box {g} covers a taken cell")
            ancestors = {nv_id(a_)[0] for a_ in shapes(ot).get(g).iterancestors() if etree.QName(a_).localname == "grpSp"}
        elif len(grown) > 1:
            diffs.append(f"slide {n} (s{k}): more than one grown box {grown}")
        # code review round 2, N1: Q1 reads drawn bounds (rotation and group flips) for shapes and destinations
        allowed = allowed_removals(s_sh, _occ(st), o_sh, _occ(ot), _hidden_ids(st), _slide_area(sp), _turned_ids(st), set(grown))
        for i in removed:
            if i not in allowed:
                diffs.append(f"slide {n} (s{k}): shape {i} ({etree.QName(s_sh[i]).localname}) missing")
        for i, el in o_sh.items():
            if i not in s_sh:
                continue  # added shapes are footers (declared)
            if _sppr(el, op, name) != _sppr(s_sh[i], sp, sname):
                diffs.append(f"slide {n} (s{k}): shape {i} properties differ (fill, line, geometry, crop or media)")
            if o_bx.get(i) != s_bx.get(i):
                ob, sb = o_bx.get(i), s_bx.get(i)
                if ob and sb and _within(sb, ob) and removed_text and _within(ob, _union([sb] + removed_text)):
                    widened.add(i)  # the declared title widening (or a group grown with it)
                elif len(grown) == 1 and (i == grown[0] or i == backing or (i in ancestors and _within(sb, ob))):
                    pass  # the declared R3 growth: the body, its own backing, their enclosing groups
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
