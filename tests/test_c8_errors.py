"""C8: unusable files raise their code without exhausting memory; outline caps."""

import io
import json
import random
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from deckfill import OutlineError, PlanError, TemplateError, package, parse_outline, plan_deck, read_template

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures" / "out"

CASES = [
    ("legacy.pptx", "legacy_ppt"),
    ("encrypted.pptx", "encrypted"),
    ("not-powerpoint.pptx", "not_pptx"),
    ("dangling-relationship.pptx", "bad_file"),
    ("zip-bomb.pptx", "too_big"),
    ("lying-size.pptx", "bad_file"),
    ("billion-laughs.pptx", "bad_file"),
    ("no-body.pptx", "no_text_layout"),
    ("damaged.pptx", "bad_file"),
]


@pytest.mark.parametrize("name,code", CASES)
def test_refusal_codes(name, code, tpl):
    with pytest.raises(TemplateError) as e:
        read_template(tpl(name), name)
    assert e.value.code == code


def test_not_a_zip_at_all():
    with pytest.raises(TemplateError) as e:
        read_template(b"%PDF-1.7 hello", "x.pptx")
    assert e.value.code == "not_pptx"


def test_over_the_file_cap_is_too_big():
    assert package.MAX_FILE == 100 * 1024 * 1024  # D1b rev 5
    with pytest.raises(TemplateError) as e:
        read_template(b"PK\x03\x04" + bytes(package.MAX_FILE), "big.pptx")
    assert e.value.code == "too_big"


def test_uncompressed_total_cap(tmp_path):
    """D1b rev 5: 150 MB in the spec, lowered by the seat to 130 MB to hold C12's 1.5 GB heap bar
    (decisions.tsv). A template declaring 160 MB uncompressed is too_big, at a ratio and file size
    well inside their own caps."""
    assert package.MAX_TOTAL == 130 * 1024 * 1024
    src = zipfile.ZipFile(io.BytesIO(open(FIX / "wui-tung.pptx", "rb").read()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in src.namelist():
            z.writestr(n, src.read(n))
        rnd = random.Random(1)
        for k in range(4):  # 4 x 40 MB, each about 20:1
            data = bytearray(40 * 1024 * 1024)
            for i in range(0, len(data), 12):
                data[i] = rnd.randrange(256)
            z.writestr(f"ppt/media/big{k}.bin", bytes(data))
    with pytest.raises(TemplateError) as e:
        read_template(buf.getvalue(), "total.pptx")
    assert e.value.code == "too_big"


MEMORY_PROBE = """
import resource, sys, json
sys.path.insert(0, %r)
from deckfill import read_template, TemplateError
data = open(sys.argv[1], 'rb').read()
code = None
try:
    read_template(data, 'x.pptx')
except TemplateError as e:
    code = e.code
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps({"code": code, "rss_mb": rss / (1024 * 1024) if sys.platform == 'darwin' else rss / 1024}))
"""


@pytest.mark.parametrize("name", ["zip-bomb.pptx", "lying-size.pptx", "billion-laughs.pptx"])
def test_bombs_stay_under_300_mb(name):
    r = subprocess.run(
        [sys.executable, "-c", MEMORY_PROBE % str(ROOT / "src"), str(ROOT / "fixtures" / "out" / name)],
        capture_output=True, text=True, check=True,
    )
    res = json.loads(r.stdout)
    print(name, res)
    assert res["code"] in ("too_big", "bad_file")
    assert res["rss_mb"] < 300


def test_outline_cap():
    with pytest.raises(OutlineError) as e:
        parse_outline("## a\n" + "- x\n" * 20000)
    assert e.value.code == "too_long"


def test_slide_cap(tpl):
    info = read_template(tpl("typed.pptx"), "t.pptx")
    text = "".join(f"## s{i}\n- x\n" for i in range(201))
    with pytest.raises(PlanError) as e:
        plan_deck(info, parse_outline(text))
    assert e.value.code == "too_many_slides"


def test_no_slides(tpl):
    info = read_template(tpl("typed.pptx"), "t.pptx")
    with pytest.raises(OutlineError) as e:
        plan_deck(info, parse_outline("just a line\nanother"))
    assert e.value.code == "no_slides"


def test_python_pptx_parser_does_not_expand_entities():
    """python-pptx's own parser: entities off; deckfill also refuses any DOCTYPE first."""
    from pptx.oxml import parse_xml

    root = parse_xml(b'<!DOCTYPE x [<!ENTITY e "EXPANDED">]><x>&e;</x>')
    assert "EXPANDED" not in (root.text or "")


# ---------------------------------------------------------------------------------------------
# Codex round 1


def test_f2_xml_found_by_content_type_not_extension(tpl):
    """A layout stored as .dat is still XML: it reads, and the XML caps and DOCTYPE rule hold."""
    read_template(tpl("xml-renamed.pptx"), "r.pptx")
    with pytest.raises(TemplateError) as e:
        read_template(tpl("xml-renamed-doctype.pptx"), "r.pptx")
    assert e.value.code == "bad_file" and "doctype" in e.value.detail
    with pytest.raises(TemplateError) as e:
        read_template(tpl("xml-renamed-big.pptx"), "r.pptx")
    assert e.value.code == "too_big" and "xml part" in e.value.detail


def _many_members(n: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        for k in range(n):
            z.writestr(f"m/{k}", b"")
    return buf.getvalue()


def _no_zipfile(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ZipFile built before the member preflight")

    monkeypatch.setattr(package.zipfile, "ZipFile", boom)


def test_f3_member_cap_checked_before_zipfile(monkeypatch):
    data = _many_members(package.MAX_MEMBERS + 500)
    _no_zipfile(monkeypatch)
    with pytest.raises(TemplateError) as e:
        read_template(data, "many.pptx")
    assert e.value.code == "too_big"


def test_f3_end_record_that_understates_the_count(monkeypatch):
    data = bytearray(_many_members(package.MAX_MEMBERS + 500))
    eocd = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, eocd + 8, 1, 1)  # entries on this disk, entries in total
    _no_zipfile(monkeypatch)
    with pytest.raises(TemplateError) as e:
        read_template(bytes(data), "lie.pptx")
    assert e.value.code == "too_big"


def test_f3_zip64_count(monkeypatch):
    data = _many_members(70_000)  # more than 0xFFFF entries: Python writes ZIP64 end records
    assert b"PK\x06\x06" in data[-200:]
    _no_zipfile(monkeypatch)
    with pytest.raises(TemplateError) as e:
        read_template(data, "zip64.pptx")
    assert e.value.code == "too_big"


def test_f5_package_root_relationship_must_resolve(tpl):
    with pytest.raises(TemplateError) as e:
        read_template(tpl("root-missing.pptx"), "root.pptx")
    assert e.value.code == "bad_file" and "missing" in e.value.detail
