"""C3 template kept, C5 integrity and package graph, C6 no empty boxes, C11 .potx."""

import socket

import pytest
from lxml import etree
from conftest import outline_text
from oracle import (
    A, P, P14, R, RT_SLIDE, kept_part_problems, new_parts, parts_of, read_deck, rels_of, slide_order, xml,
)

from deckfill import TemplateError, fill, parse_outline, plan_deck, read_template
from deckfill.package import check_integrity

FILLABLE = [
    "typed.pptx", "custom.pptx", "contradict.pptx", "two-masters.pptx", "no-two.pptx", "no-section.pptx",
    "no-title.pptx", "only-content.pptx", "small-body.pptx", "small-body-insets.pptx", "nowrap.pptx",
    "footer-active.pptx", "footer-mixed.pptx", "footer-two-masters.pptx", "footer-fixed-date.pptx",
    "footer-hf.pptx", "external-link.pptx", "sections.pptx", "wui-tung.pptx", "wui-tung.potx",
    "rels-order.pptx", "view-outline.pptx", "footer-local.pptx", "xml-renamed.pptx",
]


def make(data, name="t.pptx", text=None):
    info = read_template(data, name)
    plan = plan_deck(info, parse_outline(text or outline_text("reference")))
    return fill(data, name, plan)


@pytest.mark.parametrize("name", FILLABLE)
def test_c3_every_kept_part_unchanged(name, tpl):
    data = tpl(name)
    out = make(data, name)
    assert kept_part_problems(data, out) == []
    extra = [n for n in new_parts(data, out) if not n.startswith("ppt/slides/")]
    assert extra == []


def test_c3_kept_relationships_byte_identical(tpl):
    """Relationships out of Id order and absolute targets come back as the template wrote them."""
    data = tpl("rels-order.pptx")
    out = make(data, "rels-order.pptx")
    ip, op = parts_of(data), parts_of(out)
    kept = [n for n in ip if n.startswith(("ppt/slideMasters/_rels/", "ppt/slideLayouts/_rels/"))]
    assert kept and all(op[n] == ip[n] for n in kept)
    assert b'Target="/ppt/theme/' in op["ppt/slideMasters/_rels/slideMaster1.xml.rels"]


@pytest.mark.parametrize("name", FILLABLE)
def test_c3_slide_size_and_no_run_formatting(name, tpl):
    data = tpl(name)
    out = make(data, name)
    ip, op = parts_of(data), parts_of(out)
    size = lambda parts: xml(parts["ppt/presentation.xml"]).find("{%s}sldSz" % P).attrib  # noqa: E731
    assert dict(size(ip)) == dict(size(op))
    for s in read_deck(out):
        for rpr in s.run_props:
            if rpr is None:
                continue
            assert rpr.get("sz") is None
            for tag in ("latin", "ea", "cs", "solidFill", "gradFill"):
                assert rpr.find("{%s}%s" % (A, tag)) is None


def test_c3_sections_package_graph(tpl):
    data = tpl("sections.pptx")
    out = make(data)
    ip, op = parts_of(data), parts_of(out)
    in_media = sorted(n for n in ip if n.startswith("ppt/media/"))
    out_media = sorted(n for n in op if n.startswith("ppt/media/"))
    assert len(in_media) == 2 and len(out_media) == 1  # the shared image stays, the slide-only one goes
    assert not any(n.startswith("ppt/notesSlides/") for n in op)  # sample notes gone
    lay = "ppt/slideLayouts/slideLayout2.xml"
    assert any(t.startswith("ppt/slides/") for (_, t, _) in rels_of(ip, lay).values())
    assert not any(ty == RT_SLIDE for (ty, _, _) in rels_of(op, lay).values())
    root = xml(op[lay])
    assert root.find(".//{%s}hlinkClick" % A) is None
    # the shared image is still drawn on the layout
    assert root.find(".//{%s}blip" % A) is not None


def test_c5_sections_no_reference_to_removed_slide(tpl):
    data = tpl("sections.pptx")
    out = make(data)
    op = parts_of(out)
    pres = xml(op["ppt/presentation.xml"])
    assert pres.find("{%s}custShowLst" % P) is None
    assert pres.find(".//{%s}sectionLst" % P14) is None
    new_ids = {s.get("id") for s in pres.iter("{%s}sldId" % P)}
    in_ids = {s.get("id") for s in xml(parts_of(data)["ppt/presentation.xml"]).iter("{%s}sldId" % P)}
    # every slide relationship in the package points at a slide of the output
    out_slides = set(slide_order(op))
    for name in op:
        if name.endswith(".rels"):
            continue
        for _, (ty, t, ext) in rels_of(op, name).items():
            if ty == RT_SLIDE:
                assert t in out_slides
    assert len(new_ids) == len(read_deck(out))
    assert in_ids  # the input had slides to remove


@pytest.mark.parametrize("name", FILLABLE)
def test_c5_integrity_passes_on_every_output(name, tpl):
    assert check_integrity(parts_of(make(tpl(name), name))) == []


@pytest.mark.parametrize("name", ["dangling-relationship.pptx", "missing-embed.pptx", "missing-target.pptx"])
def test_c5_broken_templates_refused(name, tpl):
    with pytest.raises(TemplateError) as e:
        read_template(tpl(name), name)
    assert e.value.code == "bad_file"


def test_c5_external_link_kept_and_never_fetched(tpl, monkeypatch):
    calls = []

    def no_net(*a, **k):
        calls.append(a)
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(socket, "create_connection", no_net)
    monkeypatch.setattr(socket, "getaddrinfo", no_net)
    data = tpl("external-link.pptx")
    out = make(data)
    op = parts_of(out)
    rels = rels_of(op, "ppt/slideLayouts/slideLayout2.xml")
    assert ("https://example.com/never-fetch", True) in [(t, ext) for (_, t, ext) in rels.values()]
    assert xml(op["ppt/slideLayouts/slideLayout2.xml"]).find(".//{%s}hlinkClick" % A) is not None
    assert calls == []


def _rezip(parts):
    import zipfile as zf
    from io import BytesIO

    buf = BytesIO()
    with zf.ZipFile(buf, "w") as z:
        for n, d in parts.items():
            z.writestr(n, d)
    return buf.getvalue()


def _swap_first_two(rels: bytes) -> bytes:
    root = xml(rels)
    a, b = root[0], root[1]
    root.remove(b)
    a.addprevious(b)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _absolute_first_target(rels: bytes, base: str) -> bytes:
    import posixpath

    root = xml(rels)
    e = root[0]
    e.set("Target", "/" + posixpath.normpath(posixpath.join(base, e.get("Target"))))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


MASTER_RELS = "ppt/slideMasters/_rels/slideMaster1.xml.rels"
LINKED_RELS = "ppt/slideLayouts/_rels/slideLayout2.xml.rels"  # sections: also links to a sample slide


@pytest.mark.parametrize(
    "name, rels, part, edit",
    [
        ("typed.pptx", MASTER_RELS, "ppt/slideMasters/slideMaster1.xml", "reorder"),
        ("typed.pptx", MASTER_RELS, "ppt/slideMasters/slideMaster1.xml", "absolute"),
        ("sections.pptx", LINKED_RELS, "ppt/slideLayouts/slideLayout2.xml", "reorder"),
        ("sections.pptx", LINKED_RELS, "ppt/slideLayouts/slideLayout2.xml", "absolute"),
    ],
)
def test_f15_reordered_or_rewritten_relationships_are_caught(name, rels, part, edit, tpl):
    """Codex round 2, F15: two relationships swapped, or a target rewritten to an equal absolute
    form, in a kept part's relationships must fail C3, beside an authorised link removal too."""
    data = tpl(name)
    out = make(data, name)
    assert kept_part_problems(data, out) == []
    parts = parts_of(out)
    if edit == "reorder":
        parts[rels] = _swap_first_two(parts[rels])
    else:
        parts[rels] = _absolute_first_target(parts[rels], part.rsplit("/", 1)[0])
    assert f"changed relationships of {part}" in kept_part_problems(data, _rezip(parts))


@pytest.mark.parametrize("name", FILLABLE)
def test_c6_no_empty_placeholders(name, tpl):
    for s in read_deck(make(tpl(name), name)):
        for ptype, idx, has_text in s.placeholders:
            assert has_text or ptype in ("sldNum", "ftr", "dt"), (s.n, ptype, idx)


def test_c11_potx_fills_as_presentation(tpl):
    out = make(tpl("wui-tung.potx"), "wui-tung.potx")
    ct = parts_of(out)["[Content_Types].xml"].decode()
    assert "presentationml.presentation.main+xml" in ct
    assert "presentationml.template.main+xml" not in ct
    assert read_deck(out)[0].title == "匯通物流 2027 年度計劃"
    info = read_template(tpl("wui-tung.potx"), "wui-tung.potx")
    assert info.kind == "potx"


# ---------------------------------------------------------------------------------------------
# Codex round 1


def test_f6_outline_view_reference_to_a_sample_slide(tpl):
    """viewProps.xml is a generic XML part: its outline-view link to a removed slide must go."""
    data = tpl("view-outline.pptx")
    out = make(data, "view-outline.pptx")
    parts = parts_of(out)
    assert check_integrity(parts) == []
    view = parts["ppt/viewProps.xml"]
    assert b"<p:sld " not in view and b"rIdV1" not in view  # the outline entry went; an empty sldLst is valid
    assert "ppt/_rels/viewProps.xml.rels" not in parts or b"slides/" not in parts["ppt/_rels/viewProps.xml.rels"]


def test_f11_damage_beside_an_authorised_link_edit_is_caught(tpl):
    """sections: a layout links to a sample slide, so the fill may remove that link. Any other change
    to the same layout, here a shape deleted, must still fail C3."""
    import zipfile as zf
    from io import BytesIO

    from oracle import removed_slide_links

    data = tpl("sections.pptx")
    out = make(data, "sections.pptx")
    assert kept_part_problems(data, out) == []
    _, links = removed_slide_links(parts_of(data))
    layout = next(src for src, _ in links if "slideLayouts/" in src)
    parts = parts_of(out)
    root = xml(parts[layout])
    tree = root.find(".//{%s}spTree" % P)
    shapes = [sp for sp in tree if sp.tag == "{%s}sp" % P]
    tree.remove(shapes[-1])
    parts[layout] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    buf = BytesIO()
    with zf.ZipFile(buf, "w") as z:
        for n, d in parts.items():
            z.writestr(n, d)
    assert f"changed {layout}" in kept_part_problems(data, buf.getvalue())


@pytest.mark.parametrize("name", FILLABLE)
def test_f12_no_text_outside_placeholders(name, tpl):
    """Every text on every output slide sits in a placeholder (D4): text boxes, tables, groups."""
    out = make(tpl(name), name)
    assert [(s.n, s.loose_text) for s in read_deck(out) if s.loose_text] == []


def test_f12_a_text_box_on_a_slide_is_caught(tpl):
    import zipfile as zf
    from io import BytesIO

    out = make(tpl("typed.pptx"), "typed.pptx")
    parts = parts_of(out)
    name = slide_order(parts)[1]
    root = xml(parts[name])
    box = etree.fromstring(
        '<p:sp xmlns:p="%s" xmlns:a="%s"><p:nvSpPr><p:cNvPr id="900" name="TextBox"/><p:cNvSpPr txBox="1"/>'
        "<p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:p><a:r><a:t>LOOSE</a:t></a:r></a:p></p:txBody></p:sp>" % (P, A)
    )
    root.find(".//{%s}spTree" % P).append(box)
    parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    buf = BytesIO()
    with zf.ZipFile(buf, "w") as z:
        for n, d in parts.items():
            z.writestr(n, d)
    assert read_deck(buf.getvalue())[1].loose_text == ["LOOSE"]
