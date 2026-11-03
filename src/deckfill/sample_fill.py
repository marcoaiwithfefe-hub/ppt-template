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
from .cjk import has_chinese, needs_split, stretches
from .package import RT_SLIDE, check_integrity
from .sample import (
    Styles,
    _is_hidden,
    cjk_rpr,
    clearing,
    donor,
    grown_groups,
    has_text,
    level2_written,
    normalise_alternates,
    shape_id,
    to_local,
    walk,
)
from .sample_plan import MAX_XML
from .template import FOOTER_TYPES, footer_ok, ph_of, ph_type
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
    normalise_alternates(csld)  # code review F1: the fallback branches only, as the reader classified them
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


def _line(ppr, spec, size: int, text: str):
    """Rev 9 T2: the paragraph's a:lnSpc when T2 changes it (scaled to the written size, the Chinese floors); the
    a:pPr is made when the paragraph has none. Returns the a:pPr, or None when there is none to write."""
    want = spec.ln_written(size, has_chinese(text))
    if want is None or want == spec.ln_written(spec.size, False):
        return ppr
    if ppr is None:
        ppr = etree.Element(q("a:pPr"))
    for old in ppr.findall(q("a:lnSpc")):
        ppr.remove(old)
    ln = etree.Element(q("a:lnSpc"))
    etree.SubElement(ln, q("a:spcPts" if want[0] == "pts" else "a:spcPct"), val=str(want[1]))
    ppr.insert(0, ln)
    return ppr


def _write(sp, sbox, bf, l2_ppr, face: str) -> None:
    """Replace a destination box's paragraphs (D12 text): each written paragraph copies the donor paragraph's a:pPr
    (level-2 paragraphs take the box's level-2 properties when defined, else the donor's with lvl="1"), with rev 9 T2's
    line spacing; each run the donor run's a:rPr (a field's, for a field-only box), with the plan's size when the box
    shrinks. Rev 9 T1: in a Latin-only face, a paragraph holding Chinese is cut into Chinese and other stretches, each
    its own run, the Chinese ones in face (sample.cjk_rpr)."""
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
        spec = sbox.lvl1 if lvl == 1 else sbox.lvl2
        size = bf.sizes[0] if lvl == 1 else bf.sizes[1]
        ppr = _line(ppr, spec, size or spec.size, text)
        if ppr is not None:
            p.append(ppr)
        segs = stretches(text) if needs_split(sbox.faces[lvl - 1], text) else [(False, text)]
        for zh, seg in segs:
            r = etree.SubElement(p, q("a:r"))
            if zh:
                rpr = cjk_rpr(d_rpr, face, sbox.display)
            else:
                rpr = copy.deepcopy(d_rpr) if d_rpr is not None else etree.Element(q("a:rPr"))
                rpr.tag = q("a:rPr")
            if size:
                rpr.set("sz", str(size))
            r.append(rpr)
            etree.SubElement(r, q("a:t")).text = seg


def _put_xfrm(sp, local) -> None:
    x, y, cx, cy = local
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


def _set_box(sp, chain, box) -> None:
    """Widen a title box to the union of its fragments, written in the shape's own coordinates."""
    local = to_local(box, chain)
    _put_xfrm(sp, local)
    _grow_groups(sp, local)


def _set_boxes(moves) -> None:
    """R3: a grown body box and its own backing, (walked shape, slide-space box) each, written in their own (shared)
    coordinates; their groups grow once to hold both (sample.grow_in_groups checked the siblings)."""
    locals_ = [to_local(box, w.chain) for w, box in moves]
    for (w, _), local in zip(moves, locals_):
        _put_xfrm(w.el, local)
    x1, y1 = min(b[0] for b in locals_), min(b[1] for b in locals_)
    x2, y2 = max(b[0] + b[2] for b in locals_), max(b[1] + b[3] for b in locals_)
    _grow_groups(moves[0][0].el, (x1, y1, x2 - x1, y2 - y1))


def _grow_groups(el, box) -> None:
    """A widened or grown box inside a group: each enclosing group's child extent grows to hold it, at the group's
    own scale, so the group's declared bounds still contain every child (renderers redraw a group from those
    bounds). The arithmetic is sample.grown_groups, the one the planner checks siblings with (R3)."""
    xfs, chain = [], []
    parent = el.getparent()
    while parent is not None and parent.tag == q("p:grpSp"):
        xf = parent.find(q("p:grpSpPr")).find(q("a:xfrm"))
        if xf is None:
            break
        parts = [xf.find(q("a:" + t)) for t in ("off", "ext", "chOff", "chExt")]
        if any(p is None for p in parts):
            break
        off, ext, choff, chext = parts
        xfs.append(parts)
        chain.append(((int(off.get("x")), int(off.get("y"))), (int(ext.get("cx")), int(ext.get("cy"))),
                      (int(choff.get("x")), int(choff.get("y"))), (int(chext.get("cx")), int(chext.get("cy")))))
        parent = parent.getparent()
    new = grown_groups(chain, box) if chain else []
    for (off, ext, choff, chext), ((ox, oy), (ex, ey), (cx0, cy0), (cex, cey)) in zip(xfs, new or []):
        off.set("x", str(ox))
        off.set("y", str(oy))
        ext.set("cx", str(ex))
        ext.set("cy", str(ey))
        choff.set("x", str(cx0))
        choff.set("y", str(cy0))
        chext.set("cx", str(cex))
        chext.set("cy", str(cey))


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


SHAPES = tuple(q("p:" + t) for t in ("sp", "pic", "grpSp", "cxnSp", "graphicFrame", "contentPart"))


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
        if not footer_ok(el):
            out[t] = None  # Edge 1 and round 3: a footer whose idx or box does not parse is never copied
            continue
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
            _write(w.el, S.box(bf.sid), bf, level2_written(w.el, styles, para), plan.cjk_face)
            if bf.role == "echo":  # rev 9 T3: one line at its own size, its box (and bleed) kept
                w.el.find(q("p:txBody")).find(q("a:bodyPr")).set("wrap", "none")
            if bf.box is not None and bf.backing:
                _set_boxes([(w, bf.box), (walked[bf.backing[0]], bf.backing[1])])
            elif bf.box is not None:
                _set_box(w.el, w.chain, bf.box)
        if len(S.title) > 1:
            _raise_title(walked[S.title[0]].el, [walked[sid].el for sid in S.title[1:]])
        for sid in S.title[1:]:  # the other title fragments
            _remove(walked[sid].el)
            removed.add(sid)
        # everything that received no outline text is cleared (hidden shapes included): Q1 chips and R5 rectangular
        # backings under 8% go whole, nothing behind a destination that kept its text goes (sample.clearing)
        gone, emptied = clearing(S, ps.boxes, area)
        for sid, w in walked.items():
            if sid in fills or sid in removed:
                continue
            if sid in gone:
                _remove(w.el)
                removed.add(sid)
            elif sid in emptied:
                _clear_text(w.el)
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
        written += len(etree.tostring(slide._element, encoding="utf-8", xml_declaration=False))  # as saved (E1)
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
