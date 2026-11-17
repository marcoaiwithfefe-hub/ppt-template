"""C39 (Chinese face, T1) and C40 (Chinese line height, T2) on sample-latin-font, for both cjk_face values.

C39: every written Chinese stretch in a Latin-only face is its own run with the chosen face in a:latin and a:ea,
effective zero tracking and no italic, lang zh-HK, and b="1" only on display boxes; other stretches keep the donor
a:rPr apart from sz; boxes whose face covers Chinese, and boxes with no named face, are written as before. C40: the
written line spacing follows T2 and the estimate uses it. Expectations are written from the fixture's design."""

import copy
import io
import json
import zipfile

import pytest
from lxml import etree

from conftest import FIX, ROOT
from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill.web import Session
from rev9_oracle import any_chinese, chinese, cjk_problems, effective, expected_ln, paragraph_ln, run_chain, run_size, runs_of
from sample_oracle import a, level_chain, nv_id, p, parts_of, slides, tree_of, walk, xml

NAME = "sample-latin-font.pptx"
OUTLINE = (ROOT / "tests" / "outlines" / "sample" / "latin-font.md").read_text(encoding="utf-8")
OVR = {1: "s2", 2: "s3", 3: "s4", 4: "s5", 5: "s6"}
FACES = ("PingFang HK", "Microsoft JhengHei")
SPLIT = {101, 111, 201, 301, 501, 511, 601, 611}  # Latin-only faces
DISPLAY = {101, 201, 301, 401, 501, 601}  # effective size at or above 4% of the slide height
KEEP = {211, 311, 401, 411}  # Arial Unicode MS, theme PingFang TC, 微軟正黑體 in a:ea, no named face


def run_fill(face, text=OUTLINE, ovr=OVR):
    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    plan = plan_deck(info, parse_outline(text), ovr, route="sample", cjk_face=face)
    return data, info, plan, fill(data, NAME, plan)


def donors(src: bytes) -> dict:
    """Source box id -> its first run's a:rPr (the donor)."""
    sp_ = parts_of(src)
    out = {}
    for name in slides(sp_):
        for el in walk(tree_of(sp_[name])):
            sid, _ = nv_id(el)
            r = next(el.iter(a("r")), None)
            if r is not None:
                out[sid] = r.find(a("rPr"))
    return out


def canon(rpr, drop=("sz",)) -> bytes:
    e = copy.deepcopy(rpr) if rpr is not None else etree.Element(a("rPr"))
    for k in drop:
        e.attrib.pop(k, None)
    return etree.tostring(e, method="c14n")


def face_problems(out: bytes, src: bytes, face: str) -> list[str]:
    """The fixture-specific C39 rule (see the module docstring), plus the general rule (rev9_oracle.cjk_problems)."""
    bad = cjk_problems(out, face)
    don = donors(src)
    op = parts_of(out)
    seen = set()
    for n, name in enumerate(slides(op), start=1):
        for sp in walk(tree_of(op[name])):
            sid, _ = nv_id(sp)
            if sid not in SPLIT | KEEP or sp.find(p("txBody")) is None:
                continue
            seen.add(sid)
            for par in sp.find(p("txBody")).findall(a("p")):
                rs = runs_of(par)
                kinds = []
                for r in rs:
                    rpr = r.find(a("rPr"))
                    text = r.find(a("t")).text or ""
                    where = f"slide {n} box {sid} run {text!r}"
                    zh = any_chinese(text)
                    kinds.append(zh)
                    if sid in KEEP or not zh:
                        if canon(rpr) != canon(don[sid]):
                            bad.append(f"{where}: run properties differ from the donor's apart from sz")
                        continue
                    lat, ea = rpr.find(a("latin")), rpr.find(a("ea"))
                    if lat is None or ea is None or lat.get("typeface") != face or ea.get("typeface") != face:
                        bad.append(f"{where}: Chinese stretch not in {face!r} in both a:latin and a:ea")
                    if effective(op, name, sp, par, rpr, "spc", "0") != "0":
                        bad.append(f"{where}: effective tracking not zero")
                    if effective(op, name, sp, par, rpr, "i", "0") not in ("0", "false"):
                        bad.append(f"{where}: effective italic")
                    if rpr.get("lang") != "zh-HK":
                        bad.append(f"{where}: lang not zh-HK")
                    want_b = "1" if sid in DISPLAY else (don[sid].get("b") if don[sid] is not None else None)
                    if rpr.get("b") != want_b:
                        bad.append(f"{where}: b={rpr.get('b')!r}, want {want_b!r}")
                if sid in KEEP and len(rs) > 1:
                    bad.append(f"slide {n} box {sid}: a box whose face covers Chinese (or has none) was cut")
                if any(x == y for x, y in zip(kinds, kinds[1:])):
                    bad.append(f"slide {n} box {sid}: stretches are not maximal")
    missing = (SPLIT | KEEP) - seen
    if missing:
        bad.append(f"boxes never written: {sorted(missing)}")
    return bad


@pytest.mark.parametrize("face", FACES)
def test_c39_chinese_face(face):
    data, _, _, out = run_fill(face)
    assert face_problems(out, data, face) == []


@pytest.mark.parametrize("face", FACES)
def test_c39_extension_b_and_katakana(face):
    _, _, _, out = run_fill(face)
    op = parts_of(out)
    runs = [r for name in slides(op) for r in xml(op[name]).iter(a("r"))]
    ext_b = next(r for r in runs if "𠵱" in (r.find(a("t")).text or ""))
    kata = next(r for r in runs if "ｶﾀｶﾅ" in (r.find(a("t")).text or ""))
    assert ext_b.find(a("rPr")).find(a("ea")).get("typeface") == face
    assert all(chinese(c) for c in ext_b.find(a("t")).text)
    assert kata.find(a("rPr")).find(a("ea")).get("typeface") == "Montserrat"


def test_c39_default_face_is_microsoft_jhenghei():
    data = (FIX / NAME).read_bytes()
    plan = plan_deck(read_template(data, NAME), parse_outline(OUTLINE), OVR, route="sample")
    assert plan.cjk_face == "Microsoft JhengHei"


def test_c39_step3_line_only_when_t1_fired():
    s = Session()
    s.read((FIX / NAME).read_bytes(), NAME)
    fired = json.loads(s.plan(OUTLINE, "[]", "sample", "PingFang HK"))
    assert fired["cjk_face"] == "PingFang HK"
    english = json.loads(s.plan("# Plan 2027\nOperations\n\n## Goals\n- On time\n", "[]", "sample", "PingFang HK"))
    assert english["cjk_face"] is None
    pick = json.dumps([{"title": "Fonts", "kind": "content", "nth": 0, "count": 1, "layout": "s4", "route": "sample"}])
    covered = json.loads(s.plan("# Plan\n\n## Fonts\n- 冇字款\n", pick, "sample", "PingFang HK"))
    assert covered["slides"][1]["layout"] == "s4" and covered["cjk_face"] is None


# --- negative demos (silent break: Chinese left in a Latin face with no error) ---------------------------------------


def test_c39_negative_skipped_split(monkeypatch):
    """Mutation: the fill skips the run split; the check fails."""
    import deckfill.sample_fill as sf

    monkeypatch.setattr(sf, "stretches", lambda text: [(False, text)])
    data, _, _, out = run_fill("PingFang HK")
    bad = face_problems(out, data, "PingFang HK")
    assert any("Chinese in" in b for b in bad), bad


def _mutate(out: bytes, fn) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(out))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            b = zin.read(info.filename)
            if info.filename.startswith("ppt/slides/slide") and info.filename.endswith(".xml"):
                root = etree.fromstring(b)
                if fn(root):
                    b = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            z.writestr(info, b)
    return buf.getvalue()


def _chinese_runs(root, sid):
    for sp in root.iter(p("sp")):
        if nv_id(sp)[0] == sid:
            return [r for r in sp.iter(a("r")) if any_chinese(r.find(a("t")).text or "")]
    return []


def test_c39_negative_spc_left_to_inheritance():
    data, _, _, out = run_fill("PingFang HK")

    def drop(root):
        rs = _chinese_runs(root, 501)
        for r in rs:
            r.find(a("rPr")).attrib.pop("spc", None)
        return bool(rs)
    bad = face_problems(_mutate(out, drop), data, "PingFang HK")
    assert any("tracking" in b for b in bad), bad


def test_c39_negative_bold_on_body():
    data, _, _, out = run_fill("PingFang HK")

    def bold(root):
        rs = _chinese_runs(root, 111)
        for r in rs:
            r.find(a("rPr")).set("b", "1")
        return bool(rs)
    bad = face_problems(_mutate(out, bold), data, "PingFang HK")
    assert any("b='1'" in b for b in bad), bad


# --- the size budget counts the extra runs -------------------------------------------------------------------------

ALT = "# 計劃 Plan\n\n## 目標 Goals\n- " + "".join(f"中文{i} latin{i} " for i in range(10)) + "\n"


def _written_para_bytes(out: bytes, sid: int) -> int:
    op = parts_of(out)
    total = 0
    for name in slides(op):
        for sp in walk(tree_of(op[name])):
            if nv_id(sp)[0] == sid:
                total += sum(len(etree.tostring(par)) for par in sp.find(p("txBody")).findall(a("p")))
    return total


def test_c39_budget_counts_extra_runs(monkeypatch):
    """A line alternating Chinese and Latin ten times: the planner's per-paragraph budget is at least the bytes the
    fill writes for it; a budget that counts one run per paragraph is below them, so a cap between the two refuses
    the real plan and lets the mutated plan through although the box's written bytes put it over the cap."""
    from deckfill import sample_plan as spl

    data = (FIX / NAME).read_bytes()
    info = read_template(data, NAME)
    plan = plan_deck(info, parse_outline(ALT), {1: "s5"}, route="sample", cjk_face="PingFang HK")
    out = fill(data, NAME, plan)
    samples = {S.id: S for S in info.samples}
    real = spl.box_bytes(samples["s5"], plan.slides[1].boxes[1], "PingFang HK")
    written = _written_para_bytes(out, 511)
    assert real >= written
    total_real, _, _ = spl.plan_bytes(samples, plan.slides, "PingFang HK")
    monkeypatch.setattr(spl, "stretches", lambda text: [(False, text)])
    one_run = spl.box_bytes(samples["s5"], plan.slides[1].boxes[1], "PingFang HK")
    assert one_run < written, "the one-run budget must under-count this line"
    monkeypatch.undo()
    mutated_total = total_real - real + one_run
    cap = mutated_total + (written - one_run) // 2  # above the mutated budget, below what that plan writes
    monkeypatch.setattr(spl, "MAX_XML", cap)
    with pytest.raises(Exception) as e:
        plan_deck(info, parse_outline(ALT), {1: "s5"}, route="sample", cjk_face="PingFang HK")
    assert getattr(e.value, "code", "") == "too_big"
    monkeypatch.setattr(spl, "stretches", lambda text: [(False, text)])
    plan_deck(info, parse_outline(ALT), {1: "s5"}, route="sample", cjk_face="PingFang HK")  # the mutation lets it through
    assert mutated_total - one_run + written > cap  # the box's written bytes put that deck over the cap


# --- C40 ------------------------------------------------------------------------------------------------------------


def line_problems(out: bytes, src: bytes, plan, info) -> list[str]:
    """Every paragraph the fill wrote carries T2's line spacing, computed here from the source box: the donor's
    resolved a:lnSpc (the box's level-2 properties for a level-2 paragraph), scaled by the written size over the
    donor's effective size for that level, with the Chinese floors."""
    samples = {S.id: S for S in info.samples}
    op, sp_ = parts_of(out), parts_of(src)
    src_names, out_names = slides(sp_), slides(op)
    bad = []
    for n, ps in enumerate(plan.slides, start=1):
        S = samples[ps.layout]
        sname = src_names[S.k - 1]
        src_boxes = {nv_id(el)[0]: el for el in walk(tree_of(sp_[sname]))}
        out_boxes = {nv_id(el)[0]: el for el in walk(tree_of(op[out_names[n - 1]]))}
        for bf in ps.boxes:
            ssp, osp = src_boxes[bf.sid], out_boxes[bf.sid]
            spar = osp.find(p("txBody")).findall(a("p"))
            dpar = next(par for par in ssp.find(p("txBody")).findall(a("p")) if runs_of(par))
            drun = runs_of(dpar)[0].find(a("rPr"))
            for par in spar:
                text = "".join(r.find(a("t")).text or "" for r in runs_of(par))
                if not text.strip():
                    continue
                ppr = par.find(a("pPr"))
                lvl = int(ppr.get("lvl", "0")) + 1 if ppr is not None else 1
                if lvl == 1:
                    chain = [dpar.find(a("pPr"))] + level_chain(sp_, sname, ssp, int(dpar.find(a("pPr")).get("lvl", "0")) + 1 if dpar.find(a("pPr")) is not None else 1)
                    eff_chain = [dpar.find(a("pPr"))] + level_chain(sp_, sname, ssp, 1)
                else:
                    own = level_chain(sp_, sname, ssp, 2)
                    chain = own if any(e is not None and e.find(a("lnSpc")) is not None for e in own) else [dpar.find(a("pPr"))] + own
                    eff_chain = own
                from rev9_oracle import raw_ln
                src_ln = raw_ln(chain)
                eff = int(drun.get("sz")) if drun is not None and drun.get("sz") else next(
                    (int(e.find(a("defRPr")).get("sz")) for e in eff_chain if e is not None and e.find(a("defRPr")) is not None and e.find(a("defRPr")).get("sz")), 1800)
                written = run_size(op, out_names[n - 1], osp, par)
                want = expected_ln(src_ln, written, eff, any_chinese(text))
                got = paragraph_ln(op, out_names[n - 1], osp, par)
                if want != got:
                    bad.append(f"slide {n} box {bf.sid} {text[:12]!r}: line spacing {got}, T2 wants {want}")
    return bad


@pytest.mark.parametrize("face", FACES)
def test_c40_line_height(face):
    data, info, plan, out = run_fill(face)
    assert line_problems(out, data, plan, info) == []
    shrunk = [bf for ps in plan.slides for bf in ps.boxes if bf.sid == 611]
    assert shrunk and shrunk[0].sizes[0] and shrunk[0].sizes[0] < 2000, "611 must shrink for this check to mean something"


def test_c40_estimate_uses_written_values():
    data, info, plan, out = run_fill("PingFang HK")
    S = next(S for S in info.samples if S.id == "s6")
    sb = S.box(611)
    size = next(bf for ps in plan.slides for bf in ps.boxes if bf.sid == 611).sizes[0]
    lv = sb.fit_at(None, size, size).levels[0]
    op = parts_of(out)
    name = slides(op)[5]
    osp = next(el for el in walk(tree_of(op[name])) if nv_id(el)[0] == 611)
    got = paragraph_ln(op, name, osp, osp.find(p("txBody")).find(a("p")))
    assert got == ("pts", lv.cjk_line // 127)
    assert lv.line == (1700 * size // 2000) * 127  # a Latin paragraph: scaled, no Chinese floor


def test_c40_negative_unscaled_spcpts():
    data, info, plan, out = run_fill("PingFang HK")

    def unscale(root):
        hit = False
        for sp in root.iter(p("sp")):
            if nv_id(sp)[0] == 611:
                for pts in sp.iter(a("spcPts")):
                    if pts.getparent().tag == a("lnSpc"):
                        pts.set("val", "1700")
                        hit = True
        return hit
    assert line_problems(_mutate(out, unscale), data, plan, info) != []


def test_c40_negative_spcpct_left_at_85():
    data, info, plan, out = run_fill("PingFang HK")

    def lower(root):
        hit = False
        for sp in root.iter(p("sp")):
            if nv_id(sp)[0] == 211:
                for pct in sp.iter(a("spcPct")):
                    if pct.getparent().tag == a("lnSpc"):
                        pct.set("val", "85000")
                        hit = True
        return hit
    assert line_problems(_mutate(out, lower), data, plan, info) != []
