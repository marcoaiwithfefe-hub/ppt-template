"""Layout-route outputs for the blast-radius proof (rev 8 build): every fixture template and G0 real template
filled from every rev 7 outline on the layout route, each output part reduced to a digest (canonical XML for
XML parts, SHA-256 for binary parts). Run once with the 6a576a6 source and once with the head source; equal
digests mean the layout route is unchanged.

    .venv/bin/python qa/rev8/layout_baseline.py <src dir> <out.json>
"""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
src, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(src))
import deckfill  # noqa: E402
from deckfill import TemplateError, fill, parse_outline, plan_deck, read_template  # noqa: E402

KW = {}
import inspect  # noqa: E402

if "route" in inspect.signature(plan_deck).parameters:
    KW = {"route": "layout"}
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)


def digest(data: bytes) -> dict:
    res = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in sorted(z.namelist()):
            b = z.read(n)
            if n.endswith((".xml", ".rels")):
                try:
                    res[n] = hashlib.sha256(etree.canonicalize(etree.tostring(etree.fromstring(b, PARSER)).decode()).encode()).hexdigest()
                    continue
                except etree.XMLSyntaxError:
                    pass
            res[n] = hashlib.sha256(b).hexdigest()
    return res


outlines = {"reference": (ROOT / "fixtures/reference-outline.md").read_text(encoding="utf-8")}
for p in sorted((ROOT / "tests/outlines").glob("*.md")):
    outlines[p.stem] = p.read_bytes().decode("utf-8")
templates = sorted((ROOT / "fixtures/out").glob("*.pp*x")) + sorted((ROOT / "qa/real-templates").glob("*.p*tx"))
result = {"src": str(src), "route_kw": KW, "runs": {}}
for t in templates:
    data = t.read_bytes()
    try:
        info = read_template(data, t.name)
    except TemplateError as e:
        result["runs"][t.name] = {"error": e.code}
        continue
    for oname, text in outlines.items():
        key = f"{t.name}|{oname}"
        try:
            plan = plan_deck(info, parse_outline(text), None, **KW)
            result["runs"][key] = digest(fill(data, t.name, plan))
        except deckfill.DeckfillError as e:
            result["runs"][key] = {"error": e.code}
out.write_text(json.dumps(result, indent=0, sort_keys=True))
print(len(result["runs"]), "runs ->", out)
