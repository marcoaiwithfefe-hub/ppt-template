"""C23 look carried (stories 28, 32): every copy's background and kept shapes match its sample, only declared edits
differ; negative demos that keep shape counts each fail; automatic picks follow the D12 variety relaxation order,
user picks and continuation slides are exempt."""

import io
import re
import zipfile

import pytest

from conftest import FIX, ROOT
from deckfill import fill, parse_outline, plan_deck, read_template
from sample_look import look_diff
from test_c24_c27_sample_text import CASES, OUTLINES, run


@pytest.mark.parametrize("fixture,outline,overrides,gold", CASES, ids=[c[3] for c in CASES])
def test_c23_every_copy_matches_its_sample(fixture, outline, overrides, gold):
    data, out = run(fixture, outline, overrides)
    assert look_diff(out, data) == []


def _edit(out: bytes, name: str, fn) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(out))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            b = zin.read(info.filename)
            if info.filename == name:
                b = fn(b)
            z.writestr(info.filename, b)
    return buf.getvalue()


def _design():
    return run("sample-design.pptx", "design", None)


def test_c23_negative_changed_crop():
    data, out = _design()
    bad = _edit(out, "ppt/slides/slide1.xml", lambda b: re.sub(rb'<a:srcRect l="(\d+)"', rb'<a:srcRect l="25000"', b, count=1))
    assert bad != out
    assert any("properties differ" in d for d in look_diff(bad, data))


def test_c23_negative_swapped_media():
    data, out = _design()
    with zipfile.ZipFile(io.BytesIO(out)) as z:
        media = sorted(n for n in z.namelist() if n.startswith("ppt/media/"))
        other = z.read(media[-1])
    bad = _edit(out, media[0], lambda b: other if other != b else b + b"x")
    assert any("properties differ" in d for d in look_diff(bad, data))


def test_c23_negative_reordered_pair():
    data, out = _design()

    def swap(b):  # s2's copy: its title text box (201) moves above the first slot group (210)
        i, j = b.index(b'<p:sp><p:nvSpPr><p:cNvPr id="201"'), b.index(b'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="210"')
        end = b.index(b"</p:sp>", i) + len(b"</p:sp>")
        sp = b[i:end]
        rest = b[:i] + b[end:]
        j = rest.index(b'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="220"')
        return rest[:j] + sp + rest[j:]
    bad = _edit(out, "ppt/slides/slide2.xml", swap)
    assert any("z-order" in d for d in look_diff(bad, data))


def test_c23_negative_dropped_background():
    data, out = _design()
    bad = _edit(out, "ppt/slides/slide3.xml", lambda b: re.sub(rb"<p:bg>.*?</p:bg>", b"", b, count=1, flags=re.S))
    assert any("background" in d for d in look_diff(bad, data))


# --- variety (D12): automatic picks avoid the two previous slides' samples, then only the previous one's, then repeat


def _picks(fixture, text, overrides=None):
    data = (FIX / fixture).read_bytes()
    plan = plan_deck(read_template(data, fixture), parse_outline(text), overrides, route="sample")
    return plan


def test_c23_variety_avoids_the_two_previous():
    plan = _picks("sample-only.pptx", "".join(f"## T{i}\n- x\n\n" for i in range(6)))
    assert plan.chosen == ("s1", "s2", "s3", "s1", "s2", "s3")


def test_c23_variety_relaxes_to_the_previous_only():
    plan = _picks("sample-chart.pptx", "".join(f"## T{i}\n- x\n\n" for i in range(4)))  # two usable samples, s1 and s3
    assert plan.chosen == ("s1", "s3", "s1", "s3")


def test_c23_variety_relaxes_to_repeats():
    plan = _picks("sample-thin.pptx", "## A\n- x\n\n## B\n- y\n\n## C\n- z\n")
    assert plan.chosen == ("s1", "s1", "s1")


def test_c23_user_picks_are_never_changed_by_variety():
    plan = _picks("sample-only.pptx", "## A\n- x\n\n## B\n- y\n\n## C\n- z\n", {0: "s2", 1: "s2", 2: "s2"})
    assert plan.chosen == ("s2", "s2", "s2")


def test_c23_continuations_keep_their_pick_and_do_not_count():
    """A slide of seven bullets splits after the sixth (D5); its continuation keeps s1; the next slide avoids s1 only
    once (it is one outline slide), so it takes s2."""
    text = "## Long\n" + "".join(f"- b{i}\n" for i in range(7)) + "\n## Next\n- x\n\n## Third\n- y\n"
    plan = _picks("sample-only.pptx", text)
    assert [(s.source, s.part, s.layout) for s in plan.slides] == [(0, 0, "s1"), (0, 1, "s1"), (1, 0, "s2"), (2, 0, "s3")]
