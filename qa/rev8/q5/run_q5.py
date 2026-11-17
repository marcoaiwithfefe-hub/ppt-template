"""QA round 1 Q5: the three rev 7 G0 templates that now default to the sample route (edb-mpa2022, elderly-gov-diy,
hkust-template14), filled with fixtures/reference-outline.md on both routes and rendered with the G0b renderer.
One sheet per route and template, then one side-by-side image per template (left: layout route, right: sample route).
D11 is not changed here; Fable judges the default from these sheets.

    .venv/bin/python qa/rev8/q5/run_q5.py [subfolder]   (QA round 2: qa2, beside round 1's sheets)
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "qa" / "g0b"))
import run_g0b  # noqa: E402

OUT = ROOT / "qa" / "rev8" / "q5" / (sys.argv[1] if len(sys.argv) > 1 else "")
OUT.mkdir(parents=True, exist_ok=True)
run_g0b.OUT = OUT
SET = ["edb-mpa2022.pptx", "elderly-gov-diy.pptx", "hkust-template14.potx"]
FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)

summary = []
for name in SET:
    stem = Path(name).stem
    reps = {route: run_g0b.run(name, route, f"{stem}-{route}") for route in ("layout", "sample")}
    sheets = [Image.open(OUT / f"{stem}-{route}" / "sheet.jpg").convert("RGB") for route in ("layout", "sample")]
    band, gap = 48, 24
    w = sheets[0].width + gap + sheets[1].width
    h = band + max(s.height for s in sheets)
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    x = 0
    for route, s in zip(("layout", "sample"), sheets):
        r = reps[route]
        default = " (D11 default)" if r["default_route"] == route else ""
        d.text((x + 8, 10), f"{stem}: {route} route{default}, {len(r['slides'])} slides", fill="black", font=FONT)
        img.paste(s, (x, band))
        x += s.width + gap
    img.save(OUT / f"{stem}-both.jpg", quality=88)
    summary.append({"template": name, "default_route": reps["sample"]["default_route"],
                    "layout": {"slides": len(reps["layout"]["slides"]), "chosen": reps["layout"]["chosen"]},
                    "sample": {"slides": len(reps["sample"]["slides"]), "chosen": reps["sample"]["chosen"],
                               "flags": [s["flags"] for s in reps["sample"]["slides"]],
                               "blank_chips": len(reps["sample"].get("blank_chips", [])),
                               "new_overlaps": len(reps["sample"]["new_overlaps"]), "title_bar": reps["sample"].get("title_bar")},
                    "image": str((OUT / f"{stem}-both.jpg").relative_to(ROOT))})
    print(name, "layout", len(reps["layout"]["slides"]), "sample", len(reps["sample"]["slides"]), flush=True)
(OUT / "q5-runs.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
