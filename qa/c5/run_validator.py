"""C5 validator part: the Open XML SDK (Office 2016) on every output, beside its input.

Outputs come from qa/c5/manifest.json: the fixtures it lists, filled here with the reference
outline, and every required output of the other QA runs (G0, D10, C10, C1 page, C15). A missing
required output fails the run as incomplete, before the SDK is even needed. Each output is validated with its
input template, so the report separates errors the fill added from errors the template already
had. An output passes when every error it has is on qa/c5/allowlist.json, where each entry names
the diagnostic id, the template, why it is harmless and the evidence (spec C5).

The run fails when the outputs it validated differ from the manifest's list (code review F5). A manifest other than
qa/c5/manifest.json (a test's) writes its outputs and report beside itself, never over the evidence in qa/c5.

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def key(e: dict) -> tuple:
    return (e["id"], e.get("part"), e.get("path"))


def main() -> int:
    args = sys.argv[1:]
    manifest_path = Path(args[args.index("--manifest") + 1]) if "--manifest" in args else OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    evidence = manifest_path.resolve() == (OUT / "manifest.json").resolve()
    home = OUT if evidence else manifest_path.parent  # F5: a test manifest never overwrites the evidence report
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
    outdir = home / "out"
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
    # rev 8: sample-route outputs, each sample fixture filled from its golden outline on the sample route
    for item in manifest.get("generated_sample", []):
        name = item["template"]
        src = FIX / name
        data = src.read_bytes()
        ovr = {int(k): v for k, v in item.get("overrides", {}).items()} or None
        plan = plan_deck(read_template(data, name), parse_outline((ROOT / item["outline"]).read_text(encoding="utf-8")), ovr, route="sample")
        dst = outdir / f"{src.stem}-{item.get('name', 'sample')}-filled.pptx"
        dst.write_bytes(fill(data, name, plan))
        pairs.append((src, dst, "fixture, sample route"))
    pairs += required
    # F5: the validated set is exactly the manifest's list, one distinct output per entry
    expected = len(gen["templates"]) + len(manifest.get("generated_sample", [])) + len(manifest["required"])
    outputs = [dst for _, dst, _ in pairs]
    if len(outputs) != expected or len(set(outputs)) != expected:
        print(f"INCOMPLETE: the manifest lists {expected} outputs, the run made {len(set(outputs))} distinct ones")
        return 1

    allow = json.loads((OUT / "allowlist.json").read_text())
    results = validate(sorted({p for src, dst, _ in pairs for p in (src, dst)}))
    rows, bad = [], 0
    for src, dst, fam in pairs:
        before = {key(e) for e in results[str(src)]}
        after = results[str(dst)]
        added = [e for e in after if key(e) not in before]
        def entry(e):
            return next((a for a in allow if a["id"] == e["id"] and a["template"] == src.name
                         and a.get("part") in (None, e.get("part"))), None)

        unlisted = [e for e in after if entry(e) is None]
        used = [a for a in allow if any(entry(e) is a for e in after)]
        ok = not unlisted
        bad += not ok
        rows.append({
            "family": fam, "template": rel(src), "output": rel(dst),
            "errors_in_template": len(before), "errors_in_output": len(after), "added_by_fill": added[:20],
            "not_allowlisted": unlisted[:20], "allowlisted_by": used, "ok": ok,
        })
        provisional = [f"{a['id']} (provisional until {a.get('settled_by')})" for a in used if a.get("provisional")]
        print("PASS" if ok else "FAIL", rel(dst), f"output {len(after)} errors, added {len(added)}, unlisted {len(unlisted)}",
              f"allowlisted: {', '.join(provisional)}" if provisional else "")
    sys.path.insert(0, str(ROOT / "qa"))
    from provenance import tested

    files = sorted({p for src, dst, _ in pairs for p in (src, dst)})
    provisional = [a for a in allow if a.get("provisional")]
    if len(rows) != expected or {r["output"] for r in rows} != {rel(o) for o in outputs}:
        print(f"INCOMPLETE: {len(rows)} results for {expected} manifest outputs")
        return 1
    (home / "c5-report.json").write_text(json.dumps(
        {"tested": tested([f for f in files if f.resolve().is_relative_to(ROOT)]), "manifest": rel(manifest_path.resolve()), "manifest_outputs": expected, "validated": len(rows),
         "provisional_allowlist": provisional, "rows": rows}, indent=1, ensure_ascii=False))
    print(f"{len(rows) - bad} passed, {bad} failed, {len(rows)} of {expected} manifest outputs")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
