"""Test-side readers for rev 9 (C39, C40, G0c), written apart from deckfill: no import from deckfill.

Chinese characters, the faces that cover them, a run's resolved face, effective tracking, italic and bold, and the
T2 line spacing a written paragraph must carry, all from spec rev 9 T1 and T2."""

from __future__ import annotations

from lxml import etree

from sample_oracle import A, P, a, level_chain, nv_id, p, para_text, parts_of, rels, slides, tree_of, walk, xml

COVER = (
    "PingFang", "Heiti", "Songti", "Kaiti", "STHeiti", "STSong", "STKaiti", "Apple LiGothic", "Apple LiSung", "LiHei",
    "LiSong", "BiauKai", "Lantinghei", "Microsoft JhengHei", "Microsoft YaHei", "微軟正黑體", "微软雅黑", "PMingLiU",
    "MingLiU", "新細明體", "細明體", "DFKai-SB", "標楷體", "SimSun", "SimHei", "NSimSun", "宋体", "黑体", "DengXian",
    "等线", "FangSong", "KaiTi", "Noto Sans CJK", "Noto Serif CJK", "Noto Sans TC", "Noto Sans SC", "Noto Sans HK",
    "Noto Serif TC", "Noto Serif SC", "Noto Serif HK", "Source Han", "思源", "Arial Unicode", "GenSen",
    "jf-openhuninn", "LXGW", "Taipei Sans", "cwTeX",
)
RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0x20000, 0x323AF), (0xF900, 0xFAFF), (0x3000, 0x303F),
          (0x3100, 0x312F), (0xFF00, 0xFF64), (0xFFDD, 0xFFEF))


def chinese(ch: str) -> bool:
    return any(lo <= ord(ch) <= hi for lo, hi in RANGES)


def any_chinese(text: str) -> bool:
    return any(chinese(c) for c in text)


def covers(face: str) -> bool:
    f = (face or "").strip().lower()
    return bool(f) and any(f.startswith(c.lower()) for c in COVER)


def theme_fonts(parts, slide_name) -> dict:
    lay = next(t for typ, t, _ in rels(parts, slide_name).values() if typ.endswith("/slideLayout"))
    mas = next(t for typ, t, _ in rels(parts, lay).values() if typ.endswith("/slideMaster"))
    th = next(t for typ, t, _ in rels(parts, mas).values() if typ.endswith("/theme"))
    root = xml(parts[th])
    out = {}
    for tag, key in (("majorFont", "mj"), ("minorFont", "mn")):
        f = next(root.iter(a(tag)), None)
        for t, k in (("latin", "lt"), ("ea", "ea"), ("cs", "cs")):
            e = None if f is None else f.find(a(t))
            out[f"+{key}-{k}"] = "" if e is None else e.get("typeface", "")
    return out


def _named(el, theme) -> str:
    if el is None:
        return ""
    for t in ("ea", "latin"):
        e = el.find(a(t))
        if e is not None:
            name = e.get("typeface", "")
            name = theme.get(name, name) if name.startswith("+") else name
            if name.strip():
                return name
    return ""


def run_chain(parts, slide_name, sp, par):
    """The elements a run in this paragraph inherits from, nearest first, after its own a:rPr: the paragraph's
    a:defRPr, then the level chain's a:defRPr (box list style, layout and master, or the default text style)."""
    ppr = par.find(a("pPr"))
    n = int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1
    out = [None if ppr is None else ppr.find(a("defRPr"))]
    out += [None if e is None else e.find(a("defRPr")) for e in level_chain(parts, slide_name, sp, n)]
    return out


def face(parts, slide_name, sp, par, rpr, theme) -> str:
    for el in [rpr] + run_chain(parts, slide_name, sp, par):
        name = _named(el, theme)
        if name:
            return name
    return ""


def effective(parts, slide_name, sp, par, rpr, attr: str, default: str) -> str:
    for el in [rpr] + run_chain(parts, slide_name, sp, par):
        if el is not None and el.get(attr) is not None:
            return el.get(attr)
    return default


def runs_of(par):
    return [c for c in par if c.tag in (a("r"), a("fld"))]


def cjk_problems(out: bytes, cjk_face: str) -> list[str]:
    """G0c and C39's general rule: every run holding a Chinese character is either in a face that covers Chinese and
    was not cut, or is a cut stretch: Chinese characters only, the chosen face in a:latin and a:ea, effective zero
    tracking, no italic, lang zh-HK."""
    op = parts_of(out)
    bad = []
    for n, name in enumerate(slides(op), start=1):
        theme = theme_fonts(op, name)
        for sp in walk(tree_of(op[name])):
            if etree.QName(sp).localname != "sp" or sp.find(p("txBody")) is None:
                continue
            sid, _ = nv_id(sp)
            for par in sp.find(p("txBody")).findall(a("p")):
                for r in runs_of(par):
                    t = r.find(a("t"))
                    text = "" if t is None else (t.text or "")
                    if not any_chinese(text):
                        continue
                    rpr = r.find(a("rPr"))
                    lat = None if rpr is None else rpr.find(a("latin"))
                    ea = None if rpr is None else rpr.find(a("ea"))
                    cut = lat is not None and ea is not None and lat.get("typeface") == ea.get("typeface") == cjk_face
                    where = f"slide {n} box {sid} run {text!r}"
                    if cut:
                        if not all(chinese(c) for c in text):
                            bad.append(f"{where}: a cut stretch holds non-Chinese characters")
                        if effective(op, name, sp, par, rpr, "spc", "0") != "0":
                            bad.append(f"{where}: tracking not zero")
                        if effective(op, name, sp, par, rpr, "i", "0") not in ("0", "false"):
                            bad.append(f"{where}: italic")
                        if rpr.get("lang") != "zh-HK":
                            bad.append(f"{where}: lang not zh-HK")
                    else:
                        named = face(op, name, sp, par, rpr, theme)
                        if named and not covers(named):  # a run with no named face is written as before (T1)
                            bad.append(f"{where}: Chinese in {named!r}")
    return bad


# ---------------------------------------------------------------------------------------------------------------------
# T2: the line spacing a written paragraph carries


def raw_ln(chain):
    """('pts', hundredths of a point) or ('pct', thousandths of a percent) from the nearest a:lnSpc, else None."""
    for e in chain:
        el = None if e is None else e.find(a("lnSpc"))
        if el is None:
            continue
        pts, pct = el.find(a("spcPts")), el.find(a("spcPct"))
        if pts is not None:
            return ("pts", int(pts.get("val")))
        if pct is not None:
            v = pct.get("val", "100000")
            return ("pct", int(float(v[:-1]) * 1000) if v.endswith("%") else int(v))
    return None


def expected_ln(src_ln, written: int, eff: int, is_chinese: bool):
    """T2 on one paragraph: spcPts scaled by written over effective size, floored to a hundredth, raised to 1.1 times
    the written size on a Chinese paragraph; spcPct below 90% raised to 90% on a Chinese paragraph."""
    if src_ln is None:
        return None
    kind, v = src_ln
    if kind == "pts":
        w = v * written // eff
        if is_chinese:
            w = max(w, -(-11 * written // 10))
        return ("pts", w)
    return ("pct", max(v, 90000) if is_chinese else v)


def paragraph_ln(parts, slide_name, sp, par):
    ppr = par.find(a("pPr"))
    n = int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1
    return raw_ln([ppr] + level_chain(parts, slide_name, sp, n))


def run_size(parts, slide_name, sp, par) -> int:
    r = next(iter(runs_of(par)), None)
    rpr = None if r is None else r.find(a("rPr"))
    if rpr is not None and rpr.get("sz"):
        return int(rpr.get("sz"))
    for e in run_chain(parts, slide_name, sp, par):
        if e is not None and e.get("sz"):
            return int(e.get("sz"))
    return 1800
