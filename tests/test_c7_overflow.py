"""C7: a slide that will not fit is split, warned or marked "check this slide" (D5)."""

from oracle import deck_lines, read_deck

from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.plan import height

LONG = [
    "本地送貨準時率由九成二升到九成七，試行人工智能排程系統",
    "葵涌倉存貨周轉由四十五日減到三十五日，引入新貨架系統",
    "大灣區新增三條跨境路線，先試深圳東莞再擴展到佛山",
    "培訓四十位司機使用新系統，每月檢討送貨準時率報告",
    "加裝車隊定位裝置，客戶可以即時追蹤貨件送達時間",
    "年中檢討會議檢視成本同進度，必要時調整第四季預算",
]
SIX_LONG = "## 六點\n" + "\n".join(f"- {t}" for t in LONG)
MEDIUM = [t[:14] for t in LONG]  # one line each on a full-width body
SIX_MEDIUM = "## 六點\n" + "\n".join(f"- {t}" for t in MEDIUM)


def plan_for(name, text, overrides=None, tpl=None):
    data = tpl(name)
    info = read_template(data, name)
    return data, info, plan_deck(info, parse_outline(text), overrides)


def items_in(plan):
    return [(s.title, [it.text for col in s.columns for it in col]) for s in plan.slides]


def test_small_body_splits_six_long_bullets_each_part_within_estimate(tpl):
    data, info, plan = plan_for("small-body.pptx", SIX_LONG, tpl=tpl)
    assert len(plan.slides) > 1
    assert all(s.fit == "split" for s in plan.slides)
    lay = info.layout(plan.slides[0].layout)
    fit = lay.body(lay.main_body).fit
    for s in plan.slides:
        assert height(s.columns[0], fit) <= fit.height
    texts = [t for _, ts in items_in(plan) for t in ts]
    assert texts == LONG
    deck = read_deck(fill(data, "s.pptx", plan))
    assert [s.title for s in deck[1:]] == ["六點（續）"] * (len(deck) - 1)


def test_insets_and_spacing_split_earlier(tpl):
    text = "## 四點\n" + "\n".join(f"- {t}" for t in MEDIUM[:4])
    _, _, plain = plan_for("small-body.pptx", text, tpl=tpl)
    _, _, insets = plan_for("small-body-insets.pptx", text, tpl=tpl)
    assert len(insets.slides) > len(plain.slides)


def test_nowrap_marks_check_and_gives_no_estimate(tpl):
    _, info, plan = plan_for("nowrap.pptx", SIX_LONG, tpl=tpl)
    lay = info.layout(plan.slides[0].layout)
    assert lay.body(lay.main_body).fit is None
    assert [s.fit for s in plan.slides] == ["check"]
    assert [w.code for w in plan.warnings[len(plan.outline.warnings):]] == ["fit_check"]


def test_override_resplits_and_back(tpl):
    data, info, short = plan_for("small-body.pptx", SIX_MEDIUM, tpl=tpl)
    wide = next(x.id for x in info.layouts if x.name == "寬框內容")
    narrow = short.chosen[0]
    outline = parse_outline(SIX_MEDIUM)
    on_wide = plan_deck(info, outline, {0: wide})
    assert len(on_wide.slides) == 1 and on_wide.slides[0].fit == "fits"
    back = plan_deck(info, outline, {0: narrow})
    assert back == plan_deck(info, outline, {0: narrow})
    assert len(back.slides) == len(short.slides) > 1
    for p in (on_wide, back):
        assert [t for _, ts in items_in(p) for t in ts] == MEDIUM
        out = read_deck(fill(data, "s.pptx", p))
        assert [line.split(" L1 ")[1] for line in deck_lines(out) if " L1 " in line] == MEDIUM


def test_eight_short_bullets_give_six_plus_two(tpl):
    text = "## 八點\n" + "\n".join(f"- {c}" for c in "一二三四五六七八")
    _, _, plan = plan_for("typed.pptx", text, tpl=tpl)
    assert [(s.title, len(s.columns[0])) for s in plan.slides] == [("八點", 6), ("八點（續）", 2)]


def test_english_title_gets_cont(tpl):
    text = "## Plan\n" + "\n".join(f"- item {i}" for i in range(8))
    _, _, plan = plan_for("typed.pptx", text, tpl=tpl)
    assert plan.slides[1].title == "Plan (cont.)"


def test_children_stay_with_parent(tpl):
    text = "## 八點\n" + "\n".join(f"- {c}\n  - {c}之一" for c in "一二三四五六七八")
    _, _, plan = plan_for("typed.pptx", text, tpl=tpl)
    for s in plan.slides:
        items = s.columns[0]
        assert items[0].level == 1
        for a, b in zip(items, items[1:]):
            if b.level == 2:
                assert b.text.startswith(a.text if a.level == 1 else a.text[0])


def test_columns_split_the_same_way(tpl):
    left = "\n".join(f"- 左{i}" for i in range(8))
    right = "\n".join(f"- 右{i}" for i in range(3))
    _, _, plan = plan_for("typed.pptx", f"## 比較\n{left}\n||\n{right}", tpl=tpl)
    assert [(len(s.columns[0]), len(s.columns[1])) for s in plan.slides] == [(6, 3), (2, 0)]
    assert plan.slides[1].title == "比較（續）"


def test_one_paragraph_longer_than_box_is_warned_not_split(tpl):
    text = "## 長\n- " + "好長" * 200 + "\n- 短"
    _, _, plan = plan_for("small-body.pptx", text, tpl=tpl)
    assert plan.slides[0].fit == "warned"
    assert "fit_warn" in [w.code for w in plan.warnings]
    first = plan.slides[0].columns[0]
    assert len(first) == 1  # the long paragraph sits alone, unsplit
