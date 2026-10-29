"""Builds every fixture template the test suite uses into fixtures/out/ (spec Testing Decisions).

Run: .venv/bin/python fixtures/make_fixtures.py
All templates are made here from python-pptx's default template or from the 匯通物流 spike
template; none comes from the web.
"""

from __future__ import annotations

import copy
import io
import random
import re
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
}
CT_PRES = b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
CT_TEMPLATE = b"application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"

CHINESE_NAMES = [
    "標題投影片", "標題及內容", "章節標題", "兩欄內容", "比較", "只有標題",
    "空白", "含標題的內容", "含標題的圖片", "標題及直書文字", "直書標題及文字",
]


def q(name: str) -> str:
    p, local = name.split(":")
    return "{%s}%s" % (NS[p], local)


def save(prs, name: str) -> Path:
    path = OUT / name
    prs.save(path)
    return path


def layout_named(prs, name: str):
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == name:
                return lay
    raise KeyError(name)


def remove_layouts(prs, names) -> None:
    for name in names:
        lay = layout_named(prs, name)
        lay.slide_master.slide_layouts.remove(lay)


def ph_sp(el, ph_type=None, idx=None):
    for ph in el.iter(q("p:ph")):
        if ph_type is not None and ph.get("type", "obj") != ph_type:
            continue
        if idx is not None and ph.get("idx") != str(idx):
            continue
        return ph.getparent().getparent().getparent()
    return None


def set_xfrm(sp, x, y, cx, cy) -> None:
    sppr = sp.find(q("p:spPr"))
    for old in sppr.findall(q("a:xfrm")):
        sppr.remove(old)
    xfrm = etree.SubElement(sppr, q("a:xfrm"))
    sppr.insert(0, xfrm)
    etree.SubElement(xfrm, q("a:off"), x=str(x), y=str(y))
    etree.SubElement(xfrm, q("a:ext"), cx=str(cx), cy=str(cy))


def set_body_pr(sp, **attrs) -> None:
    tx = sp.find(q("p:txBody"))
    bp = tx.find(q("a:bodyPr"))
    for k, v in attrs.items():
        bp.set(k, str(v))


def set_level_spacing(sp, before_pts: int, after_pts: int) -> None:
    """Explicit level 1 and 2 paragraph spacing in the layout placeholder's list style."""
    tx = sp.find(q("p:txBody"))
    ls = tx.find(q("a:lstStyle"))
    for child in list(ls):
        ls.remove(child)
    for lvl in (1, 2):
        ppr = etree.SubElement(ls, q("a:lvl%dpPr" % lvl))
        for tag, pts in (("spcBef", before_pts), ("spcAft", after_pts)):
            s = etree.SubElement(ppr, q("a:" + tag))
            etree.SubElement(s, q("a:spcPts"), val=str(pts * 100))


def footer_sp_from_layout(layout, ph_type: str, text: str | None, field: str | None, new_id: int):
    """A slide footer placeholder the way PowerPoint writes one: the layout's placeholder with an
    empty spPr and new text."""
    src = ph_sp(layout._element, ph_type)
    sp = copy.deepcopy(src)
    sp.find(q("p:nvSpPr")).find(q("p:cNvPr")).set("id", str(new_id))
    sppr = sp.find(q("p:spPr"))
    for child in list(sppr):
        sppr.remove(child)
    tx = sp.find(q("p:txBody"))
    for p in tx.findall(q("a:p")):
        tx.remove(p)
    p = etree.SubElement(tx, q("a:p"))
    if field:
        fld = etree.SubElement(p, q("a:fld"), id="{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}", type=field)
        etree.SubElement(fld, q("a:rPr"), lang="zh-HK")
        etree.SubElement(fld, q("a:t")).text = text or "‹#›"
    else:
        r = etree.SubElement(p, q("a:r"))
        etree.SubElement(r, q("a:rPr"), lang="zh-HK")
        etree.SubElement(r, q("a:t")).text = text
    return sp


def add_footers(slide, layout, footers: dict) -> None:
    tree = slide._element.find(q("p:cSld")).find(q("p:spTree"))
    next_id = 100
    for t, (text, field) in footers.items():
        tree.append(footer_sp_from_layout(layout, t, text, field, next_id))
        next_id += 1


def bullets_slide(prs, layout_name: str, title: str, lines):
    lay = layout_named(prs, layout_name)
    s = prs.slides.add_slide(lay)
    s.shapes.title.text = title
    body = [ph for ph in s.placeholders if ph.placeholder_format.idx != 0]
    if body and lines:
        tf = body[0].text_frame
        tf.text = lines[0]
        for line in lines[1:]:
            tf.add_paragraph().text = line
    return s


def png(color, size=(40, 30)) -> io.BytesIO:
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    b.seek(0)
    return b


def zip_edit(src: Path, dst: Path, edits: dict, add: dict | None = None) -> Path:
    """Copy a zip, replacing members by function or bytes, adding members."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in edits:
                e = edits[info.filename]
                data = e(data) if callable(e) else e
                if data is None:
                    continue
            zout.writestr(info.filename, data)
        for name, data in (add or {}).items():
            zout.writestr(name, data)
    return dst


# ---------------------------------------------------------------------------------------------


def make_wui_tung() -> Path:
    path = OUT / "wui-tung.pptx"
    subprocess.run([sys.executable, str(HERE / "make_template.py"), str(path)], check=True, capture_output=True)
    (HERE / "wui-tung-template.pptx").write_bytes(path.read_bytes())
    return path


def make_potx(src: Path) -> Path:
    def ct(data: bytes) -> bytes:
        return data.replace(CT_PRES, CT_TEMPLATE)

    return zip_edit(src, OUT / "wui-tung.potx", {"[Content_Types].xml": ct})


def make_typed() -> Path:
    return save(Presentation(), "typed.pptx")


def make_custom() -> Path:
    prs = Presentation()
    for lay, name in zip(prs.slide_layouts, CHINESE_NAMES):
        el = lay._element
        el.attrib.pop("type", None)
        el.find(q("p:cSld")).set("name", name)
    two = prs.slide_layouts[3]._element
    tree = two.find(q("p:cSld")).find(q("p:spTree"))
    left, right = ph_sp(two, "obj", 1), ph_sp(two, "obj", 2)
    # right column wider than the left, so neither size nor XML order gives left-to-right
    set_xfrm(left, 457200, 1600200, 3657600, 4525963)
    set_xfrm(right, 4572000, 1600200, 4114800, 4525963)
    # right column first in XML order
    tree.remove(right)
    left.addprevious(right)
    return save(prs, "custom.pptx")


def make_contradict() -> Path:
    """A twoObj layout that holds only one body."""
    prs = Presentation()
    two = prs.slide_layouts[3]._element
    sp = ph_sp(two, "obj", 2)
    sp.getparent().remove(sp)
    return save(prs, "contradict.pptx")


def second_master(src: Path, dst: Path, prefix: str = "B ") -> Path:
    """Duplicate master 1, its theme and its layouts as master 2 (zip level)."""
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    layout_names = sorted(
        (n for n in parts if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", n)),
        key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)),
    )
    offset = len(layout_names)
    m1_rels = parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"].decode()
    m2_rels = m1_rels
    for n in layout_names:
        i = int(re.search(r"(\d+)\.xml", n).group(1))
        m2_rels = m2_rels.replace(f"slideLayout{i}.xml\"", f"slideLayout{i + offset}.xml\"")
    m2_rels = m2_rels.replace("theme1.xml", "theme2.xml")
    parts["ppt/slideMasters/_rels/slideMaster2.xml.rels"] = m2_rels.encode()
    m2 = etree.fromstring(parts["ppt/slideMasters/slideMaster1.xml"])
    for lid in m2.iter(q("p:sldLayoutId")):
        lid.set("id", str(int(lid.get("id")) + 1000))
    parts["ppt/slideMasters/slideMaster2.xml"] = etree.tostring(m2, xml_declaration=True, encoding="UTF-8", standalone=True)
    parts["ppt/theme/theme2.xml"] = parts["ppt/theme/theme1.xml"]
    ct_add = []
    for n in layout_names:
        i = int(re.search(r"(\d+)\.xml", n).group(1))
        el = etree.fromstring(parts[n])
        csld = el.find(q("p:cSld"))
        csld.set("name", prefix + (csld.get("name") or ""))
        parts[f"ppt/slideLayouts/slideLayout{i + offset}.xml"] = etree.tostring(
            el, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        rels = parts[f"ppt/slideLayouts/_rels/slideLayout{i}.xml.rels"].decode().replace("slideMaster1.xml", "slideMaster2.xml")
        parts[f"ppt/slideLayouts/_rels/slideLayout{i + offset}.xml.rels"] = rels.encode()
        ct_add.append(
            f'<Override PartName="/ppt/slideLayouts/slideLayout{i + offset}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        )
    ct_add.append(
        '<Override PartName="/ppt/slideMasters/slideMaster2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
    )
    ct_add.append(
        '<Override PartName="/ppt/theme/theme2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
    )
    ct = parts["[Content_Types].xml"].decode().replace("</Types>", "".join(ct_add) + "</Types>")
    parts["[Content_Types].xml"] = ct.encode()
    prels = parts["ppt/_rels/presentation.xml.rels"].decode()
    prels = prels.replace(
        "</Relationships>",
        '<Relationship Id="rIdM2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="slideMasters/slideMaster2.xml"/></Relationships>',
    )
    parts["ppt/_rels/presentation.xml.rels"] = prels.encode()
    pres = etree.fromstring(parts["ppt/presentation.xml"])
    lst = pres.find(q("p:sldMasterIdLst"))
    new = etree.SubElement(lst, q("p:sldMasterId"))
    new.set("id", str(2147483648 + 5000))
    new.set(q("r:id"), "rIdM2")
    parts["ppt/presentation.xml"] = etree.tostring(pres, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in parts.items():
            z.writestr(n, d)
    return dst


def make_two_masters() -> Path:
    tmp = save(Presentation(), "_base-two-masters.pptx")
    return second_master(tmp, OUT / "two-masters.pptx")


def make_no_two() -> Path:
    prs = Presentation()
    remove_layouts(prs, ["Two Content", "Comparison", "Content with Caption"])
    return save(prs, "no-two.pptx")


def make_no_section() -> Path:
    prs = Presentation()
    remove_layouts(prs, ["Section Header", "Title Only"])
    return save(prs, "no-section.pptx")


def make_no_title() -> Path:
    prs = Presentation()
    remove_layouts(prs, ["Title Slide"])
    return save(prs, "no-title.pptx")


def make_only_content() -> Path:
    prs = Presentation()
    remove_layouts(
        prs,
        ["Title Slide", "Section Header", "Two Content", "Comparison", "Title Only", "Content with Caption",
         "Picture with Caption", "Title and Vertical Text", "Vertical Title and Text"],
    )
    return save(prs, "only-content.pptx")


def make_no_body() -> Path:
    prs = Presentation()
    remove_layouts(
        prs,
        ["Title and Content", "Section Header", "Two Content", "Comparison", "Content with Caption",
         "Picture with Caption", "Title and Vertical Text", "Vertical Title and Text"],
    )
    return save(prs, "no-body.pptx")


def short_body_layouts(prs, insets: bool) -> None:
    """Title and Content gets a short body box (the default content layout); the vertical-text
    layout becomes a wide horizontal content layout to override to."""
    short = layout_named(prs, "Title and Content")
    sp = ph_sp(short._element, "obj", 1)
    set_xfrm(sp, Inches(0.5), Inches(1.6), Inches(9), Inches(1.6))
    if insets:
        set_body_pr(sp, lIns=Inches(0.6), rIns=Inches(0.6), tIns=Inches(0.3), bIns=Inches(0.3))
        set_level_spacing(sp, 12, 12)
    else:
        set_level_spacing(sp, 0, 0)
    wide = layout_named(prs, "Title and Vertical Text")
    wel = wide._element
    wel.find(q("p:cSld")).set("name", "寬框內容")
    wsp = ph_sp(wel, "body", 1)
    for bp in wsp.iter(q("a:bodyPr")):
        bp.attrib.pop("vert", None)
    set_xfrm(wsp, Inches(0.5), Inches(1.6), Inches(9), Inches(5.4))
    set_level_spacing(wsp, 0, 0)


def make_small_body() -> Path:
    prs = Presentation()
    short_body_layouts(prs, insets=False)
    return save(prs, "small-body.pptx")


def make_small_body_insets() -> Path:
    prs = Presentation()
    short_body_layouts(prs, insets=True)
    return save(prs, "small-body-insets.pptx")


def make_nowrap() -> Path:
    prs = Presentation()
    sp = ph_sp(layout_named(prs, "Title and Content")._element, "obj", 1)
    set_body_pr(sp, wrap="none")
    return save(prs, "nowrap.pptx")


def make_footer_active() -> Path:
    prs = Presentation()
    lay = layout_named(prs, "Title and Content")
    s = bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    add_footers(s, lay, {"sldNum": ("‹#›", "slidenum"), "ftr": ("匯通物流有限公司", None), "dt": ("29/10/2026", "datetime1")})
    return save(prs, "footer-active.pptx")


def make_footer_mixed() -> Path:
    prs = Presentation()
    t = prs.slides.add_slide(layout_named(prs, "Title Slide"))
    t.shapes.title.text = "封面"
    lay = layout_named(prs, "Title and Content")
    s = bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    add_footers(s, lay, {"sldNum": ("‹#›", "slidenum"), "ftr": ("內部文件", None)})
    return save(prs, "footer-mixed.pptx")


def make_footer_two_masters() -> Path:
    base = second_master(save(Presentation(), "_base-footer-two.pptx"), OUT / "_two-footer.pptx")
    prs = Presentation(base)
    a = layout_named(prs, "Title and Content")
    b = layout_named(prs, "B Title and Content")
    sa = bullets_slide(prs, "Title and Content", "甲", ["甲內容"])
    add_footers(sa, a, {"ftr": ("甲公司", None)})
    sb = bullets_slide(prs, "B Title and Content", "乙", ["乙內容"])
    add_footers(sb, b, {"ftr": ("乙公司", None)})
    return save(prs, "footer-two-masters.pptx")


def make_footer_fixed_date() -> Path:
    prs = Presentation()
    lay = layout_named(prs, "Title and Content")
    s = bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    add_footers(s, lay, {"dt": ("2026 年 10 月", None)})
    return save(prs, "footer-fixed-date.pptx")


def make_footer_hf() -> Path:
    prs = Presentation()
    m = prs.slide_masters[0]._element
    hf = etree.Element(q("p:hf"), hdr="0", dt="0", ftr="0")
    m.find(q("p:txStyles")).addprevious(hf)
    # the layout's slide-number placeholder holds the field, as PowerPoint's own layouts do
    return save(prs, "footer-hf.pptx")


def make_missing_embed() -> Path:
    prs = Presentation()
    scratch = prs.slides.add_slide(prs.slide_layouts[6])
    pic = scratch.shapes.add_picture(png("red"), Inches(1), Inches(1))
    el = copy.deepcopy(pic._element)
    el.find(".//" + q("a:blip")).set(q("r:embed"), "rId999")
    prs.slide_masters[0].shapes._spTree.append(el)
    ids = prs.slides._sldIdLst
    prs.part.drop_rel(ids[0].rId)
    ids.remove(ids[0])
    return save(prs, "missing-embed.pptx")


def hyperlink_shape(target_rid: str, text: str, action: str | None = None):
    sp = etree.fromstring(
        f'<p:sp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}">'
        '<p:nvSpPr><p:cNvPr id="90" name="Link"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        '<p:spPr><a:xfrm><a:off x="457200" y="6400800"/><a:ext cx="2743200" cy="276999"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        '<p:txBody><a:bodyPr wrap="none"/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-HK" sz="1000">'
        f'<a:hlinkClick r:id="{target_rid}"/></a:rPr><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'
    )
    if action:
        sp.find(".//" + q("a:hlinkClick")).set("action", action)
    return sp


def make_external_link() -> Path:
    prs = Presentation()
    lay = layout_named(prs, "Title and Content")
    rid = lay.part.relate_to("https://example.com/never-fetch", RT.HYPERLINK, is_external=True)
    lay.shapes._spTree.append(hyperlink_shape(rid, "公司網站"))
    return save(prs, "external-link.pptx")


def make_missing_target() -> Path:
    src = make_typed()

    def rels(data: bytes) -> bytes:
        return data.replace(
            b"</Relationships>",
            b'<Relationship Id="rIdGhost" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            b'Target="../media/ghost.png"/></Relationships>',
        )

    return zip_edit(src, OUT / "missing-target.pptx", {"ppt/slideLayouts/_rels/slideLayout2.xml.rels": rels})


def make_dangling() -> Path:
    prs = Presentation()
    bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    src = save(prs, "_base-dangling.pptx")

    def prels(data: bytes) -> bytes:
        root = etree.fromstring(data)
        for rel in list(root):
            if rel.get("Type") == RT.SLIDE:
                root.remove(rel)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    return zip_edit(src, OUT / "dangling-relationship.pptx", {"ppt/_rels/presentation.xml.rels": prels})


def make_sections() -> Path:
    prs = Presentation()
    content = layout_named(prs, "Title and Content")
    s1 = bullets_slide(prs, "Title and Content", "第一張", ["甲"])
    s2 = bullets_slide(prs, "Title and Content", "第二張", ["乙"])
    s3 = bullets_slide(prs, "Title and Content", "第三張", ["丙"])
    for s, note in ((s1, "講者備註一"), (s2, "講者備註二"), (s3, "講者備註三")):
        s.notes_slide.notes_text_frame.text = note
    shared = s1.shapes.add_picture(png((10, 80, 200)), Inches(8), Inches(0.2))
    s2.shapes.add_picture(png((200, 80, 10)), Inches(8), Inches(0.2))
    shared_part = s1.part.related_part(shared._element.blip_rId)
    rid_img = content.part.relate_to(shared_part, RT.IMAGE)
    pic = copy.deepcopy(shared._element)
    pic.find(".//" + q("a:blip")).set(q("r:embed"), rid_img)
    content.shapes._spTree.append(pic)
    rid_sl = content.part.relate_to(s1.part, RT.SLIDE)
    content.shapes._spTree.append(hyperlink_shape(rid_sl, "返回第一張", "ppaction://hlinksldjump"))
    pres = prs.part._element
    ids = list(prs.slides._sldIdLst)
    ext_lst = etree.SubElement(pres, q("p:extLst"))
    ext = etree.SubElement(ext_lst, q("p:ext"), uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}")
    sl = etree.SubElement(ext, q("p14:sectionLst"), nsmap={"p14": NS["p14"]})
    for name, members, gid in (("開場", ids[:1], "{4E1F7A1C-0000-4000-8000-000000000001}"),
                               ("內容", ids[1:], "{4E1F7A1C-0000-4000-8000-000000000002}")):
        sec = etree.SubElement(sl, q("p14:section"), name=name, id=gid)
        lst = etree.SubElement(sec, q("p14:sldIdLst"))
        for sid in members:
            etree.SubElement(lst, q("p14:sldId"), id=sid.get("id"))
    cs_lst = etree.Element(q("p:custShowLst"))
    cs = etree.SubElement(cs_lst, q("p:custShow"), name="短版", id="0")
    sld_lst = etree.SubElement(cs, q("p:sldLst"))
    for sid in ids[:2]:
        etree.SubElement(sld_lst, q("p:sld")).set(q("r:id"), sid.rId)
    pres.find(q("p:defaultTextStyle")).addprevious(cs_lst)
    return save(prs, "sections.pptx")


def make_encrypted(src: Path) -> Path:
    from msoffcrypto.format.ooxml import OOXMLFile

    out = io.BytesIO()
    with open(src, "rb") as f:
        OOXMLFile(f).encrypt("password", out)
    path = OUT / "encrypted.pptx"
    path.write_bytes(out.getvalue())
    return path


def make_legacy_ppt() -> Path:
    """OLE compound file header with a 'PowerPoint Document' stream name, renamed .pptx."""
    header = bytearray(512)
    header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<HHH", header, 24, 0x3E, 3, 0xFFFE)
    entry = bytearray(128)
    name = "PowerPoint Document".encode("utf-16-le") + b"\x00\x00"
    entry[0 : len(name)] = name
    struct.pack_into("<H", entry, 64, len(name))
    entry[66] = 2
    path = OUT / "legacy.pptx"
    path.write_bytes(bytes(header) + bytes(entry) * 4 + bytes(4096))
    return path


def make_not_pptx() -> Path:
    path = OUT / "not-powerpoint.pptx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    return path


def make_zip_bomb(src: Path) -> Path:
    """A valid template plus a 400 MB member of zeros (declared and actual)."""
    path = OUT / "zip-bomb.pptx"
    zip_edit(src, path, {})
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        with z.open("ppt/media/bomb.bin", "w", force_zip64=True) as f:
            chunk = bytes(1 << 20)
            for _ in range(400):
                f.write(chunk)
    return path


def make_lying_size(src: Path) -> Path:
    """A member whose central directory and local header say 1000 bytes; it holds 40 MB."""
    path = OUT / "lying-size.pptx"
    zip_edit(src, path, {})
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("ppt/media/liar.bin", bytes(40 << 20))
    data = bytearray(path.read_bytes())
    name = b"ppt/media/liar.bin"
    # local file header: signature, then uncompressed size at offset 22
    lh = data.find(b"PK\x03\x04" + b"\x14\x00")
    while lh != -1:
        nlen = struct.unpack_from("<H", data, lh + 26)[0]
        if bytes(data[lh + 30 : lh + 30 + nlen]) == name:
            struct.pack_into("<I", data, lh + 22, 1000)
            break
        lh = data.find(b"PK\x03\x04", lh + 4)
    cd = data.find(b"PK\x01\x02")
    while cd != -1:
        nlen = struct.unpack_from("<H", data, cd + 28)[0]
        if bytes(data[cd + 46 : cd + 46 + nlen]) == name:
            struct.pack_into("<I", data, cd + 24, 1000)
            break
        cd = data.find(b"PK\x01\x02", cd + 4)
    path.write_bytes(bytes(data))
    return path


BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
 <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
 <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
 <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
 <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
 <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">&lol9;</p:presentationPr>
"""


def make_billion_laughs(src: Path) -> Path:
    return zip_edit(src, OUT / "billion-laughs.pptx", {"ppt/presProps.xml": BILLION_LAUGHS})


def make_rels_order(src: Path) -> Path:
    """Relationships the way PowerPoint often writes them: not in Id order, and absolute
    targets. python-pptx re-sorts and relativises them on save; real templates do this
    (G0: EDB, Microsoft, USC), python-pptx-made fixtures never do."""

    def reverse(data: bytes) -> bytes:
        rels = re.findall(rb"<Relationship [^>]*/>", data)
        start, end = data.index(rels[0]), data.rindex(rels[-1]) + len(rels[-1])
        return data[:start] + b"".join(reversed(rels)) + data[end:]

    def absolute(data: bytes) -> bytes:
        return reverse(data).replace(b'Target="../theme/', b'Target="/ppt/theme/')

    with zipfile.ZipFile(src) as z:
        names = z.namelist()
    edits = {
        n: (absolute if n.startswith("ppt/slideMasters/_rels/") else reverse)
        for n in names
        if n.startswith(("ppt/slideMasters/_rels/", "ppt/slideLayouts/_rels/")) and n.endswith(".rels")
    }
    return zip_edit(src, OUT / "rels-order.pptx", edits)


def make_damaged(src: Path) -> Path:
    data = src.read_bytes()
    path = OUT / "damaged.pptx"
    path.write_bytes(data[: len(data) * 6 // 10])
    return path


# ---------------------------------------------------------------------------------------------
# Codex round 1 fixtures


def make_footer_local() -> Path:
    """F8: a sample slide carries a positioned footer of its own, on a layout with no footer box."""
    prs = Presentation()
    lay = layout_named(prs, "Title and Content")
    ftr = ph_sp(lay._element, "ftr")
    ftr.getparent().remove(ftr)
    s = bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    master_ftr = ph_sp(prs.slide_masters[0]._element, "ftr")
    sp = copy.deepcopy(master_ftr)
    sp.find(q("p:nvSpPr")).find(q("p:cNvPr")).set("id", "100")
    set_xfrm(sp, 457200, 6248400, 4114800, 365125)
    tx = sp.find(q("p:txBody"))
    for para in tx.findall(q("a:p")):
        tx.remove(para)
    r = etree.SubElement(etree.SubElement(tx, q("a:p")), q("a:r"))
    etree.SubElement(r, q("a:rPr"), lang="en-US")
    etree.SubElement(r, q("a:t")).text = "LOCAL FOOTER"
    s._element.find(q("p:cSld")).find(q("p:spTree")).append(sp)
    return save(prs, "footer-local.pptx")


RT_SLIDE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


def make_view_outline() -> Path:
    """F6: viewProps.xml keeps an outline-view reference to a sample slide."""
    prs = Presentation()
    bullets_slide(prs, "Title and Content", "示範", ["示範內容"])
    src = save(prs, "_base-view-outline.pptx")
    outline = (
        b'<p:outlineViewPr><p:cViewPr><p:scale><a:sx n="33" d="100"/><a:sy n="33" d="100"/></p:scale>'
        b'<p:origin x="0" y="0"/></p:cViewPr><p:sldLst><p:sld r:id="rIdV1" collapse="0"/></p:sldLst></p:outlineViewPr>'
    )

    def view(data: bytes) -> bytes:
        if b"xmlns:r=" not in data:
            data = data.replace(b"<p:viewPr ", b'<p:viewPr xmlns:r="%s" ' % NS["r"].encode(), 1)
        return re.sub(rb"(</p:slideViewPr>)", rb"\1" + outline, data, count=1)

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rIdV1" Type="{RT_SLIDE_REL}" Target="slides/slide1.xml"/></Relationships>'
    ).encode()
    return zip_edit(src, OUT / "view-outline.pptx", {"ppt/viewProps.xml": view}, add={"ppt/_rels/viewProps.xml.rels": rels})


CT_LAYOUT = "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"


def renamed_layout(src: Path, dst: Path, body=None) -> Path:
    """F2: slideLayout11 stored as slideLayout11.dat, its content type and every target updated."""
    old, new = "ppt/slideLayouts/slideLayout11.xml", "ppt/slideLayouts/slideLayout11.dat"
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    out = {}
    for n, d in parts.items():
        if n == old:
            n, d = new, (body(d) if body else d)
        elif n == "ppt/slideLayouts/_rels/slideLayout11.xml.rels":
            n = "ppt/slideLayouts/_rels/slideLayout11.dat.rels"
        elif n.endswith(".rels"):
            d = d.replace(b"slideLayout11.xml", b"slideLayout11.dat")
        elif n == "[Content_Types].xml":
            d = d.replace(b'PartName="/ppt/slideLayouts/slideLayout11.xml"', b'PartName="/ppt/slideLayouts/slideLayout11.dat"')
            assert b"slideLayout11.dat" in d
        out[n] = d
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in out.items():
            z.writestr(n, d)
    return dst


def make_xml_renamed(src: Path) -> list[Path]:
    def doctype(d: bytes) -> bytes:
        decl, _, rest = d.partition(b"?>")
        return decl + b'?><!DOCTYPE p:sldLayout [<!ENTITY e "x">]>' + rest

    def big(d: bytes) -> bytes:
        rnd = random.Random(5)
        pad = "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6 * 1024 * 1024))
        return d.replace(b"</p:sldLayout>", b"<!--" + pad.encode() + b"--></p:sldLayout>")

    return [
        renamed_layout(src, OUT / "xml-renamed.pptx"),
        renamed_layout(src, OUT / "xml-renamed-doctype.pptx", doctype),
        renamed_layout(src, OUT / "xml-renamed-big.pptx", big),
    ]


def make_root_missing(src: Path) -> Path:
    """F5: the package root names a part that does not exist."""
    extra = b'<Relationship Id="rIdMissing" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/missing.xml"/>'
    return zip_edit(src, OUT / "root-missing.pptx", {"_rels/.rels": lambda d: d.replace(b"</Relationships>", extra + b"</Relationships>")})


def main() -> None:
    OUT.mkdir(exist_ok=True)
    wt = make_wui_tung()
    made = [
        wt, make_potx(wt), make_typed(), make_custom(), make_contradict(), make_two_masters(),
        make_no_two(), make_no_section(), make_no_title(), make_only_content(), make_no_body(),
        make_small_body(), make_small_body_insets(), make_nowrap(), make_footer_active(),
        make_footer_mixed(), make_footer_two_masters(), make_footer_fixed_date(), make_footer_hf(),
        make_missing_embed(), make_external_link(), make_missing_target(), make_dangling(),
        make_sections(), make_encrypted(wt), make_legacy_ppt(), make_not_pptx(), make_zip_bomb(wt),
        make_lying_size(wt), make_billion_laughs(wt), make_damaged(wt), make_rels_order(wt),
        make_footer_local(), make_view_outline(), *make_xml_renamed(wt), make_root_missing(wt),
    ]
    for p in made:
        print(f"{p.name:32s} {p.stat().st_size:>10,d}")


if __name__ == "__main__":
    main()
