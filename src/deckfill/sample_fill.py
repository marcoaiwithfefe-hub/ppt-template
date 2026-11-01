"""fill on the sample-slide route (rev 8, D12 filling).

Each planned slide is a copy of its sample slide: the sample's background and shape tree, colour map override,
master-shape attributes, layout and every other relationship except notes, comments and links to slides. The outline
text goes into the boxes the plan names, with the donor paragraph and run properties and the plan's sizes; every box
that received nothing is cleared; footers are rebuilt once.
"""

from __future__ import annotations

import copy
import io
import zipfile

from lxml import etree

from .errors import TemplateError
from .fill import (
    _input_footers,
    _layout_footer_sp,
    _number_slidenum_fields,
    _next_shape_id,
    _r_attrs,
    _restore_kept,
    _update_app_xml,
    _zip,
    HLINK_TAGS,
    footer_for_type,
    remove_slides,
)
from .package import RT_SLIDE, check_integrity
from .sample import Styles, _is_hidden, _local_box, decorated, donor, has_text, level2_written, shape_id, to_local, to_slide, walk
from .sample_plan import MAX_XML
from .template import FOOTER_TYPES, ph_of, ph_type
from .xmlsafe import R_NS, q

RT_NOTES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
RT_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
RT_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
RT_THEME_OVERRIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/themeOverride"
SKIP_RELS = {RT_NOTES, RT_COMMENTS, RT_SLIDE, RT_LAYOUT}
KEEP_UNREFERENCED = {RT_LAYOUT, RT_THEME_OVERRIDE}


def _copy_sample(new_slide, src_slide) -> None:
    """The copy (D12): background and shape tree, p:clrMapOvr, showMasterSp and showMasterPhAnim, and every
    relationship except notes, comments and links to slides, remapped to the new part. show is never copied."""
    new_el, src_el = new_slide._element, src_slide._element
    csld_new = new_el.find(q("p:cSld"))
    csld = copy.deepcopy(src_el.find(q("p:cSld")))
    new_el.replace(csld_new, csld)
    old_map = new_el.find(q("p:clrMapOvr"))
    src_map = src_el.find(q("p:clrMapOvr"))
    if old_map is not None:
        new_el.remove(old_map)
    if src_map is not None:
        csld.addnext(copy.deepcopy(src_map))
    for attr in ("showMasterSp", "showMasterPhAnim"):
        if src_el.get(attr) is not None:
            new_el.set(attr, src_el.get(attr))
        elif attr in new_el.attrib:
            del new_el.attrib[attr]
    new_el.attrib.pop("show", None)
    new_part, src_part = new_slide.part, src_slide.part
    layout_rid = next(rid for rid, rel in new_part.rels.items() if rel.reltype == RT_LAYOUT)
    rid_map, dead = {}, set()
    for rid, rel in src_part.rels.items():
        if rel.reltype == RT_LAYOUT:
            rid_map[rid] = layout_rid
            continue
        if rel.reltype in SKIP_RELS:
            dead.add(rid)
            continue
        if rel.is_external:
            rid_map[rid] = new_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            rid_map[rid] = new_part.relate_to(rel.target_part, rel.reltype)
    for el in list(csld.iter()):
        for k, v in list(el.attrib.items()):
            if not k.startswith("{%s}" % R_NS):
                continue
            if v in dead:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)  # an element that uses a removed link to a slide goes with it
                break
            if v in rid_map:
                el.set(k, rid_map[v])


def _remove(el) -> None:
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _clear_text(sp) -> None:
    """A decorated shape keeps its shape and loses its text."""
    tx = sp.find(q("p:txBody"))
    if tx is None:
        return
    for p in tx.findall(q("a:p")):
        tx.remove(p)
    etree.SubElement(tx, q("a:p"))


def _write(sp, sbox, bf, l2_ppr) -> None:
    """Replace a destination box's paragraphs (D12 text): each written paragraph copies the donor paragraph's a:pPr
    (level-2 paragraphs take the box's level-2 properties when defined, else the donor's with lvl="1"), each run the
    donor run's a:rPr (a field's, for a field-only box), with the plan's size when the box shrinks."""
    para, run = donor(sp)
    d_ppr = None if para is None else para.find(q("a:pPr"))
    d_rpr = None if run is None else run.find(q("a:rPr"))
    tx = sp.find(q("p:txBody"))
    for p in tx.findall(q("a:p")):
        tx.remove(p)
    for lvl, text in bf.paras:
        p = etree.SubElement(tx, q("a:p"))
        if lvl == 1:
            ppr = copy.deepcopy(d_ppr) if d_ppr is not None else None
        else:
            ppr = copy.deepcopy(l2_ppr)
        if ppr is not None:
            p.append(ppr)
        r = etree.SubElement(p, q("a:r"))
        rpr = copy.deepcopy(d_rpr) if d_rpr is not None else etree.Element(q("a:rPr"))
        if rpr.tag != q("a:rPr"):
            rpr.tag = q("a:rPr")
        size = bf.sizes[0] if lvl == 1 else bf.sizes[1]
        if size:
            rpr.set("sz", str(size))
        r.append(rpr)
        etree.SubElement(r, q("a:t")).text = text


def _set_box(sp, chain, box) -> None:
    """Widen a title box to the union of its fragments, written in the shape's own coordinates."""
    x, y, cx, cy = to_local(box, chain)
    pr = sp.find(q("p:spPr"))
    xf = pr.find(q("a:xfrm"))
    if xf is None:
        xf = etree.Element(q("a:xfrm"))
        pr.insert(0, xf)
    off, ext = xf.find(q("a:off")), xf.find(q("a:ext"))
    if off is None:
        off = etree.SubElement(xf, q("a:off"))
    if ext is None:
        ext = etree.SubElement(xf, q("a:ext"))
    off.set("x", str(x))
    off.set("y", str(y))
    ext.set("cx", str(cx))
    ext.set("cy", str(cy))
    _grow_groups(sp, (x, y, cx, cy))


def _grow_groups(el, box) -> None:
    """A widened box inside a group: each enclosing group's child extent grows to hold it, at the group's own scale,
    so the group's declared bounds still contain every child (renderers redraw a group from those bounds)."""
    parent = el.getparent()
    while parent is not None and parent.tag == q("p:grpSp"):
        xf = parent.find(q("p:grpSpPr")).find(q("a:xfrm"))
        if xf is None:
            return
        off, ext, choff, chext = (xf.find(q("a:" + t)) for t in ("off", "ext", "chOff", "chExt"))
        if off is None or ext is None or choff is None or chext is None:
            return
        ox, oy, ex, ey = (int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))
        c0x, c0y, cex, cey = (int(choff.get("x")), int(choff.get("y")), int(chext.get("cx")), int(chext.get("cy")))
        sx, sy = (ex / cex if cex else 1.0), (ey / cey if cey else 1.0)
        bx, by, bcx, bcy = box
        u0x, u0y = min(c0x, bx), min(c0y, by)
        u1x, u1y = max(c0x + cex, bx + bcx), max(c0y + cey, by + bcy)
        if (u0x, u0y, u1x, u1y) == (c0x, c0y, c0x + cex, c0y + cey):
            return
        nox, noy = round(ox + (u0x - c0x) * sx), round(oy + (u0y - c0y) * sy)
        nex, ney = round((u1x - u0x) * sx), round((u1y - u0y) * sy)
        choff.set("x", str(u0x))
        choff.set("y", str(u0y))
        chext.set("cx", str(u1x - u0x))
        chext.set("cy", str(u1y - u0y))
        off.set("x", str(nox))
        off.set("y", str(noy))
        ext.set("cx", str(nex))
        ext.set("cy", str(ney))
        box = (nox, noy, nex, ney)
        parent = parent.getparent()


def _raise_title(dest, frags) -> None:
    """The joined title is drawn above the shapes that sat with the other fragments: inside the smallest container
    holding the whole region, the destination's branch moves to just after the last fragment's branch. Without this,
    a fragment's own backing shape (Marco's white word blocks) covers the widened title (declared with the widening)."""
    def chain(el):
        out = []
        while el is not None:
            out.append(el)
            el = el.getparent()
        return out

    dest_chain = chain(dest)
    common = None
    for anc in dest_chain[1:]:
        if all(anc in chain(f) for f in frags):
            common = anc
            break
    if common is None:
        return

    def branch(el):
        c = chain(el)
        return c[c.index(common) - 1]

    db = branch(dest)
    last = max((branch(f) for f in frags), key=lambda b: common.index(b))
    if common.index(last) > common.index(db):
        last.addnext(db)


CHIP_SHARE = 0.08  # QA round 1 Q1: a cleared chip or backing under 8% of the slide area goes
BACKING_SHARE = 0.8  # a backing holds at least 80% of the text box's area
SHAPES = tuple(q("p:" + t) for t in ("sp", "pic", "grpSp", "cxnSp", "graphicFrame", "contentPart"))


def _xywh(b) -> tuple[int, int, int, int]:
    return b.x, b.y, b.cx, b.cy


def _inside(inner, outer) -> float:
    """The share of inner's area that lies inside outer (slide-space boxes)."""
    ix = min(inner[0] + inner[2], outer[0] + outer[2]) - max(inner[0], outer[0])
    iy = min(inner[1] + inner[3], outer[1] + outer[3]) - max(inner[1], outer[1])
    a = inner[2] * inner[3]
    return (ix * iy) / a if ix > 0 and iy > 0 and a > 0 else 0.0


def _shape_kids(el):
    return list(el.iterchildren(*SHAPES))


def _visible(el) -> bool:
    """A shape that draws: not hidden, and for a group, holding a visible member."""
    if _is_hidden(el):
        return False
    if el.tag == q("p:grpSp"):
        return any(_visible(c) for c in _shape_kids(el))
    return True


def _members(g) -> int:
    return sum(1 for _ in g.iterdescendants(*SHAPES))


def _sample_footers(src_slide, layout):
    """Each footer type the sample carries: its top-level placeholder as it is, or a grouped one re-placed on the
    layout's box of that type (never at a removed grouped copy's place); None when it has no position source."""
    out = {}
    sptree = src_slide._element.find(q("p:cSld")).find(q("p:spTree"))
    for w in walk(sptree):
        el = w.el
        if etree.QName(el).localname != "sp":
            continue
        ph = ph_of(el)
        if ph is None or ph_type(ph) not in FOOTER_TYPES or ph_type(ph) in out:
            continue
        t = ph_type(ph)
        new = copy.deepcopy(el)
        if not w.top:
            _, target_ph = _layout_footer_sp(layout, t)
            if target_ph is None:
                out[t] = None
                continue
            pr = new.find(q("p:spPr"))
            for child in list(pr):
                pr.remove(child)
            nph = new.find(q("p:nvSpPr")).find(q("p:nvPr")).find(q("p:ph"))
            if target_ph.get("idx") is None:
                nph.attrib.pop("idx", None)
            else:
                nph.set("idx", target_ph.get("idx"))
        for h in [x for x in new.iter() if x.tag in HLINK_TAGS]:
            h.getparent().remove(h)
        out[t] = None if any(_r_attrs(x) for x in new.iter()) else new
    return out


def _drop_unused_rels(slide) -> None:
    used = {v for el in slide._element.iter() for k, v in el.attrib.items() if k.startswith("{%s}" % R_NS)}
    for rid, rel in list(slide.part.rels.items()):
        if rid not in used and rel.reltype not in KEEP_UNREFERENCED:
            slide.part.rels.pop(rid)


def fill_sample(info, pkg, plan) -> bytes:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(pkg.zip_bytes()))
    area = int(prs.slide_width or 9144000) * int(prs.slide_height or 6858000)
    samples = {S.id: S for S in info.samples}
    # source snapshot: the sample slides are read before D4 removes every input slide
    src = {S.id: s for S, s in zip(info.samples, list(prs.slides))}
    lay_info = {lay.id: lay for lay in info.layouts}
    masters = {str(lay.part.partname): m._element for m in prs.slide_masters for lay in m.slide_layouts}
    inputs = _input_footers(prs, lay_info)
    remove_slides(prs)
    written = 0
    for number, ps in enumerate(plan.slides, start=1):
        S = samples[ps.layout]
        src_slide = src[S.id]
        layout = src_slide.slide_layout
        slide = prs.slides.add_slide(layout)
        _copy_sample(slide, src_slide)
        tree = slide._element.find(q("p:cSld")).find(q("p:spTree"))
        members = {shape_id(g): _members(g) for g in tree.iter(q("p:grpSp"))}
        # footer placeholders inside the copy go first; D4 adds each type back once
        for w in walk(tree):
            ph = ph_of(w.el) if etree.QName(w.el).localname == "sp" else None
            if ph is not None and ph_type(ph) in FOOTER_TYPES:
                _remove(w.el)
        walked = {shape_id(w.el): w for w in walk(tree) if shape_id(w.el) is not None}
        fills = {bf.sid: bf for bf in ps.boxes}
        removed: set[int] = set()
        styles = Styles(layout._element, layout.slide_master._element, prs.part._element.find(q("p:defaultTextStyle")))
        for bf in ps.boxes:
            w = walked[bf.sid]
            para, _ = donor(w.el)
            _write(w.el, S.box(bf.sid), bf, level2_written(w.el, styles, para))
            if bf.box is not None:
                _set_box(w.el, w.chain, bf.box)
        if len(S.title) > 1:
            _raise_title(walked[S.title[0]].el, [walked[sid].el for sid in S.title[1:]])
        for sid in S.title[1:]:  # the other title fragments
            _remove(walked[sid].el)
            removed.add(sid)
        # everything that received no outline text is cleared (hidden shapes included). QA round 1 Q1: a cleared
        # shape with a fill or line under 8% of the slide goes whole, and so does a text-free shape with a fill or
        # line under 8% that holds at least 80% of a cleared text box (its backing); nothing behind a destination that
        # kept its text goes. Measured in slide space against the sample's boxes.
        dests = [bf.box or _xywh(S.box(bf.sid)) for bf in ps.boxes]
        cleared = [_xywh(b) for b in S.boxes if b.sid not in fills]

        def slide_box(w):
            local = _local_box(w.el)
            return None if local is None else to_slide(local, w.chain)

        def goes(box, backing: bool) -> bool:
            if box is None or box[2] * box[3] >= CHIP_SHARE * area:
                return False
            # behind a destination that kept its text: it backs the destination's written box, or it lies under
            # that box (the word blocks under a joined title's widened box)
            if any(_inside(d, box) >= BACKING_SHARE or _inside(box, d) >= BACKING_SHARE for d in dests):
                return False
            return not backing or any(_inside(c, box) >= BACKING_SHARE for c in cleared)

        for sid, w in walked.items():
            el = w.el
            if sid in fills or sid in removed or etree.QName(el).localname != "sp":
                continue
            if has_text(el):
                if ph_of(el) is not None or not decorated(el) or goes(slide_box(w), False):
                    _remove(el)
                    removed.add(sid)
                else:
                    _clear_text(el)
            elif ph_of(el) is None and decorated(el) and goes(slide_box(w), True):
                _remove(el)
                removed.add(sid)
        for w in walk(tree):  # placeholders left with no text (C6)
            el = w.el
            if etree.QName(el).localname == "sp" and ph_of(el) is not None and not has_text(el) and el.getparent() is not None:
                if shape_id(el) is not None:
                    removed.add(shape_id(el))
                _remove(el)
        for tag in ("a:stCxn", "a:endCxn"):
            for c in list(tree.iter(q(tag))):
                if (c.get("id") or "").isdigit() and int(c.get("id")) in removed:
                    _remove(c)
        # groups emptied by the clearing, and (Q1) groups that lost members and hold no visible member, innermost first
        for g in reversed(list(tree.iter(q("p:grpSp")))):
            kids = _shape_kids(g)
            if not kids or (_members(g) < members.get(shape_id(g), 0) and not any(_visible(c) for c in kids)):
                _remove(g)
        # footers: the sample's own first, then D4 steps 1 to 4
        own = _sample_footers(src_slide, layout)
        li = lay_info[str(layout.part.partname)]
        for t in FOOTER_TYPES:
            if t in own:
                el = own[t]
            else:
                el = footer_for_type(t, str(layout.part.partname), layout, li, inputs, masters[str(layout.part.partname)])
            if el is None:
                continue
            el.find(q("p:nvSpPr")).find(q("p:cNvPr")).set("id", str(_next_shape_id(slide._element)))
            _number_slidenum_fields(el, number)
            ext = tree.find(q("p:extLst"))
            if ext is not None:
                ext.addprevious(el)
            else:
                tree.append(el)
        _drop_unused_rels(slide)
        written += len(etree.tostring(slide._element))
        if written > MAX_XML:
            raise TemplateError("too_big", "sample route: generated slide XML over the cap")
    _update_app_xml(prs, len(plan.slides))
    out = io.BytesIO()
    prs.save(out)
    with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts = _restore_kept(pkg.parts, parts, pkg.main)
    result = _zip(parts)
    problems = check_integrity(parts)
    if problems:
        raise TemplateError("bad_file", "output failed integrity: " + "; ".join(problems[:5]))
    return result
