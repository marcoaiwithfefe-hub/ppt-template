"""C10: the page's downloads equal the CPython fill of the same template, outline and plan.

Reads qa/e2e/c9-report.json (written by tests/e2e/c9_privacy.mjs), fills the same inputs under
CPython and compares every part. Run: .venv/bin/python qa/e2e/c10_compare.py
"""

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def main() -> int:
    report = json.loads((ROOT / "qa" / "e2e" / "c9-report.json").read_text())
    outline = parse_outline((ROOT / report["session"]["outline"]).read_text(encoding="utf-8"))
    results = []
    for f in report["session"]["fills"]:
        data = (ROOT / "fixtures" / "out" / f["template"]).read_bytes()
        # rev 8 (C28): a fill records its route and its full override set, replayed here whole
        if f.get("overrides"):
            overrides = {int(k): v for k, v in f["overrides"].items()}
        else:
            overrides = {f["overrideSource"]: f["override"]} if f.get("override") else None
        this = parse_outline((ROOT / f["outline"]).read_text(encoding="utf-8")) if f.get("outline") else outline
        plan = plan_deck(read_template(data, f["template"]), this, overrides, route=f.get("route"),
                         cjk_face=f.get("cjkFace") or "Microsoft JhengHei")  # rev 9 T1: the face the page passed
        want = parts(fill(data, f["template"], plan))
        got = parts(Path(f["file"]).read_bytes())
        differ = sorted(n for n in set(want) | set(got) if want.get(n) != got.get(n))
        results.append({"template": f["template"], "route": f.get("route", "layout"), "override": f.get("override"),
                        "overrides": f.get("overrides"), "parts": len(want), "differ": differ})
        print("PASS" if not differ else "FAIL", f["template"], "override" if overrides else "", len(want), "parts", differ[:5])
    sys.path.insert(0, str(ROOT / "qa"))
    from provenance import tested

    files = [ROOT / "fixtures" / "out" / f["template"] for f in report["session"]["fills"]]
    files += [Path(f["file"]) for f in report["session"]["fills"]]
    out = {"tested": tested(files), "browser_run": report.get("tested", {}).get("commit"), "results": results}
    (ROOT / "qa" / "e2e" / "c10-report.json").write_text(json.dumps(out, indent=1))
    return 0 if all(not r["differ"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
