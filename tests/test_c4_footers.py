"""C4, silent break: footers and slide numbers follow what the template already shows (D4)."""

from conftest import outline_text
from oracle import A, para_text, read_deck

from deckfill import fill, parse_outline, plan_deck, read_template


def deck(data, name="t.pptx", overrides=None, text=None):
    info = read_template(data, name)
    plan = plan_deck(info, parse_outline(text or outline_text("reference")), overrides)
    return info, read_deck(fill(data, name, plan))


def ftext(sp):
    return "".join(para_text(p) for p in sp.iter("{%s}p" % A))


def has_field(sp, ftype=None):
    for f in sp.iter("{%s}fld" % A):
        if ftype is None or f.get("type", "").startswith(ftype):
            return True
    return False


def test_footer_active(tpl):
    _, d = deck(tpl("footer-active.pptx"))
    title, content = d[0], d[1:]
    assert title.footers == {}  # no title-class example: none (D4 step 2 skips title-class layouts)
    for s in content:
        assert set(s.footers) == {"sldNum", "ftr", "dt"}, s.n
        assert has_field(s.footers["sldNum"], "slidenum")
        assert ftext(s.footers["sldNum"]) == str(s.n)  # cached text is this slide's number
        assert ftext(s.footers["ftr"]) == "匯通物流有限公司"
        assert has_field(s.footers["dt"], "datetime")


def test_footer_mixed(tpl):
    _, d = deck(tpl("footer-mixed.pptx"))
    assert d[0].footers == {}
    for s in d[1:]:
        assert set(s.footers) == {"sldNum", "ftr"}, s.n
        assert ftext(s.footers["ftr"]) == "內部文件"


def test_footer_two_masters_each_its_own_text(tpl):
    data = tpl("footer-two-masters.pptx")
    info = read_template(data, "t.pptx")
    b_content = next(x.id for x in info.layouts if x.name == "B Title and Content")
    _, d = deck(data, overrides={1: b_content, 2: b_content})
    assert ftext(d[1].footers["ftr"]) == "乙公司"
    assert ftext(d[2].footers["ftr"]) == "乙公司"
    assert ftext(d[4].footers["ftr"]) == "甲公司"  # 八項行動 on master 1


def test_footer_fixed_date_copied_unchanged(tpl):
    _, d = deck(tpl("footer-fixed-date.pptx"))
    for s in d[1:]:
        assert set(s.footers) == {"dt"}
        assert ftext(s.footers["dt"]) == "2026 年 10 月"
        assert not has_field(s.footers["dt"])


def test_footer_hf(tpl):
    _, d = deck(tpl("footer-hf.pptx"))
    assert d[0].footers == {}  # never on a title-class layout
    for s in d[1:]:
        assert set(s.footers) == {"sldNum"}, s.n
        assert has_field(s.footers["sldNum"], "slidenum")


def test_wui_tung_no_footer_placeholder_but_master_footer_drawn(tpl):
    from oracle import parts_of, xml

    data = tpl("wui-tung.pptx")
    info, d = deck(data)
    assert all(s.footers == {} for s in d)
    assert all(lay.footers == ("dt", "ftr", "sldNum") for lay in info.layouts)
    master = xml(parts_of(data)["ppt/slideMasters/slideMaster1.xml"])
    assert any("匯通物流有限公司" in (t.text or "") for t in master.iter("{%s}t" % A))
