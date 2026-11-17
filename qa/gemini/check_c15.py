"""C15: each Gemini output holds one code block, parses with zero warnings, keeps every number from
its notes, and fills wui-tung cleanly. Run after run_c15.sh.

Run: .venv/bin/python qa/gemini/check_c15.py
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "qa" / "g0"))

from oracle import kept_part_problems, parts_of, read_deck  # noqa: E402
from run_g0 import actual_sequence, expected_sequence, same_sequence  # noqa: E402

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402
from deckfill.package import check_integrity  # noqa: E402

GEM = Path(os.environ["C15_DIR"]) if os.environ.get("C15_DIR") else ROOT / "qa" / "gemini"
CASES = ["wui-tung-report", "english-update", "meeting-summary"]  # spec C15: all three are required
NOTES = ROOT / "fixtures" / "notes"
FENCE = re.compile(r"^(```|~~~)", re.M)
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def numbers(text: str) -> list[str]:
    return sorted({n.rstrip(",") for n in NUM.findall(text)})


def missing_numbers(notes: str, outline_text: str) -> list[str]:
    """Numbers of the notes the outline does not carry, compared as whole tokens: 14 is not kept
    by 114 (Codex round 1, F14)."""
    have = set(numbers(outline_text))
    return [n for n in numbers(notes) if n not in have]


def check(name: str) -> dict:
    out = (GEM / f"{name}.out.txt").read_text(encoding="utf-8")
    notes = (NOTES / f"{name}.md").read_text(encoding="utf-8")
    fences = len(FENCE.findall(out))
    blocks = fences // 2
    inside = re.findall(r"```[^\n]*\n(.*?)```", out, re.S)
    outline_text = inside[0] if inside else out
    outline = parse_outline(outline_text)
    missing = missing_numbers(notes, outline_text)
    data = (ROOT / "fixtures" / "out" / "wui-tung.pptx").read_bytes()
    info = read_template(data, "wui-tung.pptx")
    plan = plan_deck(info, outline)
    deck_bytes = fill(data, "wui-tung.pptx", plan)
    (GEM / f"{name}.wui-tung.pptx").write_bytes(deck_bytes)
    deck = read_deck(deck_bytes)
    rec = {
        "notes": name,
        "code_blocks": blocks,
        "text_outside_block": re.sub(r"```[^\n]*\n.*?```", "", out, flags=re.S).strip(),
        "parse_warnings": [f"{w.line} {w.code}" for w in outline.warnings],
        "numbers_in_notes": numbers(notes),
        "numbers_missing": missing,
        "slides": [f"{s.title} ({s.fit})" for s in plan.slides],
        "fill_c1": same_sequence(expected_sequence(outline), actual_sequence(deck)),
        "fill_c3": kept_part_problems(data, deck_bytes),
        "fill_c5": check_integrity(parts_of(deck_bytes)),
    }
    rec["pass"] = (
        blocks == 1 and not rec["parse_warnings"] and not missing and rec["fill_c1"]
        and not rec["fill_c3"] and not rec["fill_c5"]
    )
    return rec


def main() -> int:
    absent = [n for n in CASES if not (GEM / f"{n}.out.txt").exists()]
    report = [check(n) for n in CASES if n not in absent]
    (GEM / "c15-report.json").write_text(
        json.dumps({"missing_cases": absent, "cases": report}, ensure_ascii=False, indent=1)
    )
    for n in absent:
        print(f"MISSING {n}: no Gemini output")
    for r in report:
        print(r["notes"], "PASS" if r["pass"] else "FAIL", "blocks", r["code_blocks"], "warn", r["parse_warnings"],
              "missing", r["numbers_missing"])
    return 1 if absent or not all(r["pass"] for r in report) else 0


if __name__ == "__main__":
    sys.exit(main())
