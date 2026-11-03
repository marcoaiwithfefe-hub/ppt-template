"""Negative demo for G0c's donor check (Codex rev 9 round 1 weak check): bold stripped from every cut Chinese stretch
of the Canva example fill; donor_problems must report them. Writes qa/g0c/donor-negative.txt.

    .venv/bin/python qa/g0c/donor_negative.py
"""

import importlib.util
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "qa")]
spec = importlib.util.spec_from_file_location("g0c", ROOT / "qa" / "g0c" / "run_g0c.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

from deckfill import fill, parse_outline, plan_deck, read_template  # noqa: E402

data = g.TEMPLATE.read_bytes()
g.INFO = read_template(data, g.TEMPLATE.name)
plan = plan_deck(g.INFO, parse_outline(g.OUTLINES["example"]), None, cjk_face="PingFang HK")
out = fill(data, g.TEMPLATE.name, plan)
buf = io.BytesIO()
with zipfile.ZipFile(io.BytesIO(out)) as z, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zo:
    for info in z.infolist():
        d = z.read(info.filename)
        if re.match(r"ppt/slides/slide\d+\.xml$", info.filename):
            d = re.sub(rb'(<a:rPr[^>]*lang="zh-HK"[^>]*?) b="1"', rb"\1", d)
        zo.writestr(info, d)
clean = g.donor_problems(plan, out, data, "PingFang HK")
mutated = g.donor_problems(plan, buf.getvalue(), data, "PingFang HK")
text = (f"# G0c donor check, Canva deck, example outline, PingFang HK\nfill as written: {len(clean)} problems\n"
        f"bold stripped from cut stretches: {len(mutated)} problems\n" + "\n".join(mutated) + "\n")
(ROOT / "qa" / "g0c" / "donor-negative.txt").write_text(text, encoding="utf-8")
print(text.splitlines()[1], "|", text.splitlines()[2])
sys.exit(0 if not clean and mutated else 1)
