"""C8: unusable files raise their code without exhausting memory; outline caps."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from deckfill import OutlineError, PlanError, TemplateError, parse_outline, plan_deck, read_template

ROOT = Path(__file__).resolve().parent.parent

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


def test_over_50_mb_is_too_big():
    with pytest.raises(TemplateError) as e:
        read_template(b"PK\x03\x04" + bytes(50 * 1024 * 1024), "big.pptx")
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
