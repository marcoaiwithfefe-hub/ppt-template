"""C5 validator failure demo (run: .venv/bin/python qa/failure-demos/c5_validator_demo.py): fill writes an attribute the schema does not declare on every text run.
The CPython integrity check (C5 integrity part) does not look at schema, so it passes; the Open XML
SDK validator must fail the same deck. Writes qa/failure-demos/c5-validator-{mutated,fixed}.txt."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "qa" / "failure-demos"
TMP = ROOT / "qa" / "failure-demos" / "runs"
PY = str(ROOT / ".venv" / "bin" / "python")
FILL = ROOT / "src" / "deckfill" / "fill.py"
OLD = "        r.text = text\n"
NEW = '        r.text = text\n        r._r.set("bogus", "1")\n'
MAKE = """
import sys; sys.path.insert(0, "{root}/src")
from deckfill import fill, parse_outline, plan_deck, read_template
data = open("{root}/fixtures/out/typed.pptx", "rb").read()
outline = parse_outline(open("{root}/fixtures/reference-outline.md", encoding="utf-8").read())
open(sys.argv[1], "wb").write(fill(data, "typed.pptx", plan_deck(read_template(data, "typed.pptx"), outline)))
""".format(root=ROOT)


def run(tag: str) -> str:
    deck = TMP / f"c5-demo-{tag}.pptx"
    subprocess.run([PY, "-c", MAKE, str(deck)], check=True)
    integrity = subprocess.run(
        [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_c3_c6_package.py", "-k", "c5_integrity"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()[-1]
    val = subprocess.run(
        [str(ROOT / "tools/dotnet/dotnet"), str(ROOT / "tools/validate/bin/Release/net10.0/validate.dll"), str(deck)],
        capture_output=True, text=True,
    )
    errors = json.loads(val.stdout.splitlines()[0])["errors"]
    ids = sorted({e["id"] for e in errors})
    first = errors[0]["description"] if errors else ""
    return (f"CPython C5 integrity on the same code: {integrity}\n"
            f"Open XML SDK validator on the filled typed.pptx: {len(errors)} errors {ids} {first}\n"
            f"{'FAIL' if errors else 'PASS'} C5 validator\n")


head = (f"# c5-validator: fill writes an undeclared attribute on every text run\n"
        f"# mutation in src/deckfill/fill.py: {OLD!r} -> {NEW!r}\n"
        f"# checks: pytest -k c5_integrity, then tools/validate on the filled typed.pptx\n")
TMP.mkdir(parents=True, exist_ok=True)
original = FILL.read_text(encoding="utf-8")
assert original.count(OLD) == 1
try:
    FILL.write_text(original.replace(OLD, NEW), encoding="utf-8")
    (OUT / "c5-validator-mutated.txt").write_text(head + run("mutated"), encoding="utf-8")
finally:
    FILL.write_text(original, encoding="utf-8")
(OUT / "c5-validator-fixed.txt").write_text(head + run("fixed"), encoding="utf-8")
print((OUT / "c5-validator-mutated.txt").read_text() + (OUT / "c5-validator-fixed.txt").read_text())
sys.exit(0)
