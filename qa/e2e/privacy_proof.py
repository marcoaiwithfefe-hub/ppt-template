"""Blast-radius proof of the privacy promise (D6, C9): from the saved whole-session request log,
the page made zero requests after ready.

Reads qa/e2e/c9-report.json written by tests/e2e/c9_privacy.mjs. Every request the browser saw and
every request the server received is in it, with times. After ready the only allowed entries are
the user's own clicks on fixed link-out anchors, which the test intercepts and does not follow.
Exits 1 on any other entry. Run: .venv/bin/python qa/e2e/privacy_proof.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    rep = json.loads((ROOT / "qa" / "e2e" / "c9-report.json").read_text())
    s = rep["session"]
    ready = s["tReady"]
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    anchors = set(re.findall(r'<a\s[^>]*href="(https?://[^"]+)"', html))
    norm = lambda u: u.rstrip("/")  # noqa: E731
    link_outs = {norm(a) for a in anchors}

    after = [r for r in s["requests"] if r["t"] > ready]
    page_requests = [r for r in after if not (r["type"] == "document" and norm(r["url"]) in link_outs)]
    server_after = [r for r in s["serverLog"] if r["t"] > ready]
    before_other = [r for r in s["requests"] if r["t"] <= ready and not r["url"].startswith(("http://127.0.0.1", "data:"))]
    session_s = (max(r["t"] for r in s["requests"] + s["serverLog"]) - min(r["t"] for r in s["requests"])) / 1000

    print(f"session {session_s:.0f} s; {len(s['requests'])} browser requests, {len(s['serverLog'])} server hits")
    print(f"before ready: {s['requestsBeforeReady']} requests, {len(before_other)} to another origin")
    print(f"after ready: {len(after)} browser requests, of which {len(after) - len(page_requests)} are clicked link-outs "
          f"({', '.join(sorted({r['url'] for r in after if r not in page_requests}))})")
    print(f"after ready: {len(page_requests)} page requests, {len(server_after)} server hits, "
          f"{len(s.get('violations', []))} blocked attempts")
    print(f"fills after ready: {len(s['fills'])} with downloads, plus one offline")
    failed = page_requests or server_after or before_other or s.get("violations")
    print("FAIL" if failed else "PASS: zero page requests after ready")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
