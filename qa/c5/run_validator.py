"""C5 validator part: the Open XML SDK (Office 2016) on every output, beside its input.

Outputs: every fillable fixture filled with the reference outline, every D3 fallback fixture,
the G0 fills, the D10 demo deck and the C10 browser downloads. Each output is validated with its
input template, so the report separates errors the fill added from errors the template already
had. An output passes when every error it has is on qa/c5/allowlist.json, where each entry names
the diagnostic id, the template, why it is harmless and the evidence (spec C5).

Needs the SDK at tools/dotnet (gitignored). Build once:
  tools/dotnet/dotnet build tools/validate -c Release
Run: .venv/bin/python qa/c5/run_validator.py
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
FILLABLE = [
    "typed.pptx", "custom.pptx", "contradict.pptx", "two-masters.pptx", "no-two.pptx", "no-section.pptx",
    "no-title.pptx", "only-content.pptx", "small-body.pptx", "small-body-insets.pptx", "nowrap.pptx",
    "footer-active.pptx", "footer-mixed.pptx", "footer-two-masters.pptx", "footer-fixed-date.pptx",
    "footer-hf.pptx", "external-link.pptx", "sections.pptx", "wui-tung.pptx", "wui-tung.potx", "rels-order.pptx",
]


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
    if not DOTNET.exists() or not DLL.exists():
        print("NOT RUN: Open XML SDK missing (tools/dotnet) or validator not built (tools/validate/bin)")
        return 2
    outdir = OUT / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    outline = parse_outline((ROOT / "fixtures" / "reference-outline.md").read_text(encoding="utf-8"))

    pairs: list[tuple[Path, Path]] = []  # (input template, output deck)
    for name in FILLABLE:
        src = FIX / name
        data = src.read_bytes()
        dst = outdir / f"{src.stem}-{src.suffix[1:]}-filled.pptx"
        dst.write_bytes(fill(data, name, plan_deck(read_template(data, name), outline)))
        pairs.append((src, dst))
    for g0 in sorted((ROOT / "qa" / "g0").glob("*/*-filled.pptx")):
        src = next((ROOT / "qa" / "real-templates").glob(g0.parent.name + ".*"), None)
        if src:
            pairs.append((src, g0))
    pairs.append((ROOT / "fixtures" / "wui-tung-template.pptx", ROOT / "qa" / "demo" / "wui-tung-deck.pptx"))
    for dl, tpl in (("c10-wui-tung.pptx", "wui-tung.pptx"), ("c10-typed-override.pptx", "typed.pptx")):
        if (ROOT / "qa" / "e2e" / dl).exists():
            pairs.append((FIX / tpl, ROOT / "qa" / "e2e" / dl))

    allow = json.loads((OUT / "allowlist.json").read_text())
    results = validate(sorted({p for pair in pairs for p in pair}))
    rows, bad = [], 0
    for src, dst in pairs:
        before = {key(e) for e in results[str(src)]}
        after = results[str(dst)]
        added = [e for e in after if key(e) not in before]
        unlisted = [e for e in after if not any(a["id"] == e["id"] and a["template"] == src.name for a in allow)]
        ok = not unlisted
        bad += not ok
        rows.append({
            "template": str(src.relative_to(ROOT)), "output": str(dst.relative_to(ROOT)),
            "errors_in_template": len(before), "errors_in_output": len(after), "added_by_fill": added[:20],
            "not_allowlisted": unlisted[:20], "ok": ok,
        })
        print("PASS" if ok else "FAIL", dst.relative_to(ROOT), f"output {len(after)} errors, added {len(added)}, unlisted {len(unlisted)}")
    (OUT / "c5-report.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows) - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
