"""C5 validator part: the Open XML SDK (Office 2016) on every output, beside its input.

Outputs come from qa/c5/manifest.json: the fixtures it lists, filled here with the reference
outline, and every required output of the other QA runs (G0, D10, C10, C1 page, C15). A missing
required output fails the run as incomplete, before the SDK is even needed. Each output is validated with its
input template, so the report separates errors the fill added from errors the template already
had. An output passes when every error it has is on qa/c5/allowlist.json, where each entry names
the diagnostic id, the template, why it is harmless and the evidence (spec C5).

Needs the SDK at tools/dotnet (gitignored). Build once:
  tools/dotnet/dotnet build tools/validate -c Release
Run: .venv/bin/python qa/c5/run_validator.py [--manifest <file>]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402

OUT = ROOT / "qa" / "c5"
DOTNET = ROOT / "tools" / "dotnet" / "dotnet"
DLL = ROOT / "tools" / "validate" / "bin" / "Release" / "net10.0" / "validate.dll"
FIX = ROOT / "fixtures" / "out"


def validate(files: list[Path]) -> dict[str, list[dict]]:
    run = subprocess.run([str(DOTNET), str(DLL), *map(str, files)], capture_output=True, text=True)
    results = {}
    for line in run.stdout.splitlines():
        rec = json.loads(line)
        results[rec["file"]] = rec["errors"]
    missing = [f for f in files if str(f) not in results]
    if missing:
        raise SystemExit(f"validator gave no result for {missing[:3]}; stderr: {run.stderr[-500:]}")
    return results


def key(e: dict) -> tuple:
    return (e["id"], e.get("part"), e.get("path"))


def main() -> int:
    args = sys.argv[1:]
    manifest_path = Path(args[args.index("--manifest") + 1]) if "--manifest" in args else OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    # Every required output must exist before anything is validated (Codex round 1, F13).
    required = [(ROOT / r["template"], ROOT / r["output"], r["family"]) for r in manifest["required"]]
    missing = [(fam, out) for _, out, fam in required if not out.exists()]
    for fam, out in missing:
        print(f"MISSING {out.relative_to(ROOT)} ({fam})")
    if missing:
        print(f"INCOMPLETE: {len(missing)} required outputs missing; run their QA steps first")
        return 1
    if not DOTNET.exists() or not DLL.exists():
        print("NOT RUN: Open XML SDK missing (tools/dotnet) or validator not built (tools/validate/bin)")
        return 2
    outdir = OUT / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    gen = manifest["generated"]
    outline = parse_outline((ROOT / gen["outline"]).read_text(encoding="utf-8"))

    pairs: list[tuple[Path, Path, str]] = []  # (input template, output deck, family)
    for name in gen["templates"]:
        src = FIX / name
        data = src.read_bytes()
        dst = outdir / f"{src.stem}-{src.suffix[1:]}-filled.pptx"
        dst.write_bytes(fill(data, name, plan_deck(read_template(data, name), outline)))
        pairs.append((src, dst, "fixture"))
    pairs += required

    allow = json.loads((OUT / "allowlist.json").read_text())
    results = validate(sorted({p for src, dst, _ in pairs for p in (src, dst)}))
    rows, bad = [], 0
    for src, dst, fam in pairs:
        before = {key(e) for e in results[str(src)]}
        after = results[str(dst)]
        added = [e for e in after if key(e) not in before]
        unlisted = [e for e in after if not any(a["id"] == e["id"] and a["template"] == src.name for a in allow)]
        ok = not unlisted
        bad += not ok
        rows.append({
            "family": fam, "template": str(src.relative_to(ROOT)), "output": str(dst.relative_to(ROOT)),
            "errors_in_template": len(before), "errors_in_output": len(after), "added_by_fill": added[:20],
            "not_allowlisted": unlisted[:20], "ok": ok,
        })
        print("PASS" if ok else "FAIL", dst.relative_to(ROOT), f"output {len(after)} errors, added {len(added)}, unlisted {len(unlisted)}")
    sys.path.insert(0, str(ROOT / "qa"))
    from provenance import tested

    files = sorted({p for src, dst, _ in pairs for p in (src, dst)})
    (OUT / "c5-report.json").write_text(json.dumps({"tested": tested(files), "rows": rows}, indent=1, ensure_ascii=False))
    print(f"{len(rows) - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
