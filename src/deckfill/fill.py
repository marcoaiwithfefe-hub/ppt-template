"""fill: template + plan -> .pptx bytes (D4)."""

from __future__ import annotations

import copy
import io
import zipfile

from lxml import etree

from .errors import PlanError, TemplateError
from .package import RT_SLIDE, Index, check_integrity, is_xml_name, is_xml_type, rels_name, source_of_rels
from .plan import Plan, plan_deck
from .template import FOOTER_TYPES, open_template, ph_idx, ph_of, ph_type, placeholders
from .xmlsafe import NS, R_NS, parse, q

SECTION_EXT_URI = "{521415D9-36F7-43E2-AB2F-B90AF26B5E84}"
CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
CT_NOTES = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
HLINK_TAGS = {q("a:hlinkClick"), q("a:hlinkMouseOver"), q("a:hlinkHover")}


def _r_attrs(el):
    return [(k, v) for k, v in el.attrib.items() if k.startswith("{%s}" % R_NS)]


def _has_text(sp) -> bool:
    return any((t.text or "").strip() for t in sp.iter(q("a:t")))


# ---------------------------------------------------------------------------------------------
# slide removal (D4)


def _kept_parts(package, removed: set):
    """Parts reachable from the package root without passing through a removed slide."""
    seen, stack = set(), [package._rels]
    out = []
    while stack:
        rels = stack.pop()
        for rel in rels.values():
            if rel.is_external:
                continue
            part = rel.target_part
            if part in removed or id(part) in seen:
                continue
            seen.add(id(part))
            out.append(part)
            stack.append(part.rels)
    return out


def remove_slides(prs) -> None:
    pres_part = prs.part
    pres = pres_part._element
    removed = {rel.target_part for rel in pres_part.rels.values() if rel.reltype == RT_SLIDE}
    # presentation.xml: slide list, custom shows, section list
    sld_lst = pres.find(q("p:sldIdLst"))
    if sld_lst is not None:
        for sid in list(sld_lst):
            sld_lst.remove(sid)
    for cs in pres.findall(q("p:custShowLst")):
        pres.remove(cs)
    ext_lst = pres.find(q("p:extLst"))
    if ext_lst is not None:
        for ext in list(ext_lst):
            if ext.get("uri") == SECTION_EXT_URI or ext.find(q("p14:sectionLst")) is not None:
                ext_lst.remove(ext)
        if len(ext_lst) == 0:
            pres.remove(ext_lst)
    # every kept part, presentation.xml included: drop relationships to removed slides and the
    # elements that use them (layout or master hyperlinks to a slide, outline view lists)
    for part in [pres_part] + _kept_parts(prs.part.package, removed):
        rids = [rid for rid, rel in part.rels.items() if not rel.is_external and rel.target_part in removed]
        if not rids:
            continue
        dead = set(rids)
        el_root = getattr(part, "_element", None)
        if el_root is not None:
            _drop_dead_refs(el_root, dead)
        elif is_xml_type(part.content_type) or is_xml_name(str(part.partname)):
            # an XML part python-pptx keeps as bytes, such as viewProps.xml (Codex round 1, F6)
            root = parse(part.blob, str(part.partname))
            if _drop_dead_refs(root, dead):
                part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        for rid in rids:
            part.rels.pop(rid)


def _drop_dead_refs(root, dead: set) -> bool:
    """Remove every element that uses a relationship to a removed slide. True when one went."""
    changed = False
    for el in list(root.iter()):
        if any(v in dead for _, v in _r_attrs(el)):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                changed = True
    return changed


# ---------------------------------------------------------------------------------------------
# footers (D4)


def _input_footers(prs, layout_by_id):
    """Per input slide: layout id, master index, class, and its footer shapes by type."""
    out = []
    for slide in prs.slides:
        lid = str(slide.slide_layout.part.partname)
        lay = layout_by_id.get(lid)
        found = {}
        for sp, ph in placeholders(slide._element):
            t = ph_type(ph)
            if t in FOOTER_TYPES and t not in found:
                found[t] = (sp, slide.slide_layout)
        out.append((lid, lay.master if lay else -1, lay.cls if lay else "other", found))
    return out


def _layout_footer_sp(layout, t):
    for sp, ph in placeholders(layout._element):
        if ph_type(ph) == t:
            return sp, ph
    return None, None


def _footer_from_layout(layout, t):
    """D4 step 3: the layout's own placeholder; a date only when it is a field."""
    sp, ph = _layout_footer_sp(layout, t)
    if sp is None:
        return None
    tx = sp.find(q("p:txBody"))
    if t == "dt" and (tx is None or tx.find(".//" + q("a:fld")) is None):
        return None
    if t == "ftr" and not _has_text(sp):
        return None
    new = copy.deepcopy(sp)
    sppr = new.find(q("p:spPr"))
    if sppr is not None:
        for child in list(sppr):
            sppr.remove(child)
    return new


def _place_footer(el, el_ph, t: str, src_layout, master_el, new_layout) -> bool:
    """Give a copied footer an explicit place when the new layout cannot supply one. Uses the
    footer's own xfrm, else its source layout's or the master's box of the same type. Its idx moves
    off any idx the new layout already uses. False when no place is known."""
    sppr = el.find(q("p:spPr"))
    if sppr is None:
        return False
    if sppr.find(q("a:xfrm")) is None:
        donor = None
        for root in (src_layout._element, master_el):
            for sp, ph in placeholders(root):
                if ph_type(ph) == t:
                    x = sp.find(q("p:spPr")).find(q("a:xfrm")) if sp.find(q("p:spPr")) is not None else None
                    if x is not None:
                        donor = x
                        break
            if donor is not None:
                break
        if donor is None:
            return False
        sppr.insert(0, copy.deepcopy(donor))
    used = {ph_idx(ph) for _, ph in placeholders(new_layout._element)}
    idx = ph_idx(el_ph)
    if idx in used:
        el_ph.set("idx", str(max(used | {idx}) + 1))
    return True


def _master_hf_on(master_el, t: str) -> bool:
    hf = master_el.find(q("p:hf"))
    if hf is None:
        return False
    return hf.get(t, "1") not in ("0", "false")


def idx_ok(sp) -> bool:
    """Code review round 2, Edge 1: a footer placeholder's idx is absent or a plain number. One that is neither is
    never copied onto a new slide (placing it would read the idx)."""
    ph = ph_of(sp)
    v = None if ph is None else ph.get("idx")
    return v is None or v.strip().isdigit()


def footer_for_type(t, new_lid, layout, lay_info, inputs, master_el):
    """D4 footer rules for one footer type on one new slide. Returns the shape element to add, or None."""
    same_layout = [f for (lid, _, _, f) in inputs if lid == new_lid]
    pick = None
    decided = False
    if same_layout:
        decided = True
        pick = next((f[t] for f in same_layout if t in f), None)
    elif lay_info.cls != "title":
        same_master = [f for (lid, mi, cls, f) in inputs if mi == lay_info.master and cls != "title"]
        if same_master:
            decided = True
            pick = next((f[t] for f in same_master if t in f), None)
    if decided:
        if pick is None:
            return None
        pick_sp, pick_layout = pick
        if not idx_ok(pick_sp):
            return None  # Edge 1: a borrowed footer whose idx does not parse is skipped
        target_sp, target_ph = _layout_footer_sp(layout, t)
        el = copy.deepcopy(pick_sp)
        el_ph = el.find(q("p:nvSpPr")).find(q("p:nvPr")).find(q("p:ph"))
        if target_ph is None:
            # The new layout has no box of this type, so the footer keeps the place it had on
            # its own slide (Codex round 1, F8): its own geometry, else its layout's or master's.
            if not _place_footer(el, el_ph, t, pick_layout, master_el, layout):
                return None
        elif target_ph.get("idx") is None:
            el_ph.attrib.pop("idx", None)
        else:
            el_ph.set("idx", target_ph.get("idx"))
        for h in [x for x in el.iter() if x.tag in HLINK_TAGS]:
            h.getparent().remove(h)
        if any(_r_attrs(x) for x in el.iter()):
            return None
        return el
    if lay_info.cls != "title" and _master_hf_on(master_el, t):
        return _footer_from_layout(layout, t)
    return None


def footers_for(new_lid, layout, lay_info, inputs, master_el):
    """D4 footer rules for one new slide. Returns shape elements to add."""
    out = []
    for t in FOOTER_TYPES:
        el = footer_for_type(t, new_lid, layout, lay_info, inputs, master_el)
        if el is not None:
            out.append(el)
    return out


# ---------------------------------------------------------------------------------------------


def _put(ph_sp, paras):
    """Write paragraphs (level, text) into a placeholder shape on the slide. Level 2 items are
    paragraph level 1; no font, size or colour is set."""
    tf = ph_sp.text_frame
    for i, (lvl, text) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = text
        if lvl > 1:
            p.level = 1


def _next_shape_id(slide_el) -> int:
    ids = [int(e.get("id")) for e in slide_el.iter(q("p:cNvPr")) if (e.get("id") or "").isdigit()]
    return max(ids, default=1) + 1


def _update_app_xml(prs, n: int) -> None:
    for part in prs.part.package.iter_parts():
        if str(part.partname) != "/docProps/app.xml":
            continue
        root = etree.fromstring(part.blob, etree.XMLParser(resolve_entities=False, no_network=True))
        ns = NS["ep"]
        for tag, val in (("Slides", n), ("Notes", 0), ("HiddenSlides", 0)):
            el = root.find("{%s}%s" % (ns, tag))
            if el is not None:
                el.text = str(val)
        part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _number_slidenum_fields(el, number: int) -> None:
    """A copied slide-number field keeps its source slide's cached text ("2" from a sample slide,
    "‹#›" from a layout). PowerPoint recomputes it on open, but Quick Look, Finder and Drive
    previews show the cached text, so it is set to this slide's own number."""
    for fld in el.iter(q("a:fld")):
        if fld.get("type") == "slidenum":
            t = fld.find(q("a:t"))
            if t is not None:
                t.text = str(number)


def _restore_kept(inp: dict[str, bytes], out: dict[str, bytes], main: str) -> dict[str, bytes]:
    """python-pptx re-serialises every part it saves: relationships sorted by id, absolute
    targets made relative. Where a kept part means the same as the template's (same resolved
    relationships, or equal parsed XML), the template's own bytes go back (D4: kept parts
    unchanged). Slide and notes parts are the fill's own and are left alone."""
    allowed = {main, rels_name(main), "[Content_Types].xml", "docProps/app.xml"}
    out_idx, in_idx = Index(out), Index(inp)
    restored = dict(out)
    for name, data in out.items():
        if name in allowed or name not in inp or inp[name] == data:
            continue
        source = source_of_rels(name) if name.endswith(".rels") else name
        if out_idx.content_type(source) in (CT_SLIDE, CT_NOTES):
            continue
        if name.endswith(".rels"):
            same = {(r.rid, r.type, r.target, r.external) for r in in_idx.rels(source).values()} == {
                (r.rid, r.type, r.target, r.external) for r in out_idx.rels(source).values()
            }
        elif out_idx.is_xml(name):
            # both parsed by the same parser, so equal trees serialise to equal bytes; libxml2's
            # serialiser is fast where C14N 2.0 is pure Python (5 s on a real template in the
            # browser). A false "different" only leaves python-pptx's bytes, which C3 then flags.
            same = etree.tostring(in_idx.xml(name)) == etree.tostring(out_idx.xml(name))
        else:
            same = False
        if same:
            restored[name] = inp[name]
    return restored


def _zip(parts: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()


def fill(data: bytes, filename: str, plan: Plan) -> bytes:
    info, pkg = open_template(data, filename)
    expected = plan_deck(info, plan.outline, dict(plan.overrides), route=plan.route)
    if expected != plan:
        raise PlanError("stale_plan", "plan differs from plan_deck for the same overrides")
    if plan.route == "sample":
        from .sample_fill import fill_sample

        return fill_sample(info, pkg, plan)
    from pptx import Presentation

    prs = Presentation(io.BytesIO(pkg.zip_bytes()))
    layouts = {}
    masters = {}
    for mi, master in enumerate(prs.slide_masters):
        for layout in master.slide_layouts:
            layouts[str(layout.part.partname)] = layout
            masters[str(layout.part.partname)] = master._element
    lay_info = {lay.id: lay for lay in info.layouts}
    inputs = _input_footers(prs, lay_info)
    remove_slides(prs)

    for number, ps in enumerate(plan.slides, start=1):
        layout = layouts[ps.layout]
        li = lay_info[ps.layout]
        slide = prs.slides.add_slide(layout)
        by_idx = {ph_idx(ph): sp for sp, ph in placeholders(slide._element)}
        shapes = {sh.placeholder_format.idx: sh for sh in slide.placeholders}
        keep = set()
        if ps.dest.title is not None and ps.title:
            _put(shapes[ps.dest.title], [(1, ps.title)])
            keep.add(ps.dest.title)
        body_paras = {}
        if ps.dest.subtitle and ps.subtitle:
            kind, idx = ps.dest.subtitle
            body_paras.setdefault(idx, []).extend((1, line) for line in ps.subtitle)
        for idx, items in zip(ps.dest.bodies, ps.columns):
            body_paras.setdefault(idx, []).extend((it.level, it.text) for it in items)
        for idx, paras in body_paras.items():
            if paras:
                _put(shapes[idx], paras)
                keep.add(idx)
        # placeholders that received no text are removed (D4); footers are added after
        tree = slide._element.find(q("p:cSld")).find(q("p:spTree"))
        for idx, sp in by_idx.items():
            if idx not in keep:
                tree.remove(sp)
        for el in footers_for(ps.layout, layout, li, inputs, masters[ps.layout]):
            el.find(q("p:nvSpPr")).find(q("p:cNvPr")).set("id", str(_next_shape_id(slide._element)))
            _number_slidenum_fields(el, number)
            ext = tree.find(q("p:extLst"))
            if ext is not None:
                ext.addprevious(el)
            else:
                tree.append(el)

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
