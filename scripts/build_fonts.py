"""Self-hosted fonts for the page (spec D1, D6): no font loads from another origin.

Noto Serif TC is subset to the glyphs the page itself shows (every string in docs/copy.js,
docs/prompt.txt and docs/index.html, plus ASCII and CJK punctuation). Text the user brings
(layout names, slide titles) falls back to the system's serif for glyphs outside the subset.
Newsreader is subset to Latin. Mentron Serif is copied as is. Variable axes are kept.

Sources: tools/fonts-src/ (gitignored), from github.com/google/fonts (ofl/newsreader,
ofl/notoseriftc) and the Mentron site. Run again after any copy change.

Run: .venv/bin/python scripts/build_fonts.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "fonts-src"
OUT = ROOT / "docs" / "fonts"
MENTRON = Path("/Users/marcoaiwithfefe/Desktop/AI brain/Projects/ai-agency/mentron-website/site-v3/assets/fonts")

LATIN = "U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-203A,U+2190-2193,U+2197"
CJK_PUNCT = "　，。、：；！？「」『』（）《》〈〉【】…—·‧％＋－／～"


def page_text() -> str:
    text = ""
    for name in ("copy.js", "prompt.txt", "index.html"):
        p = ROOT / "docs" / name
        if p.exists():
            text += p.read_text(encoding="utf-8")
    return text


def make(src: Path, dst: Path, text: str = "", unicodes: str = "") -> None:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = subset.load_font(str(src), opts)
    s = subset.Subsetter(opts)
    s.populate(text=text, unicodes=subset.parse_unicodes(unicodes) if unicodes else [])
    s.subset(font)
    subset.save_font(font, str(dst), opts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ascii_ = "".join(chr(c) for c in range(0x20, 0x7F))
    make(SRC / "NotoSerifTC.ttf", OUT / "noto-serif-tc-page.woff2", text=page_text() + ascii_ + CJK_PUNCT)
    make(SRC / "Newsreader.ttf", OUT / "newsreader-latin.woff2", unicodes=LATIN)
    shutil.copyfile(MENTRON / "mentron-serif-var.woff2", OUT / "mentron-serif-var.woff2")
    shutil.copyfile(MENTRON / "OFL.txt", OUT / "OFL-mentron-serif.txt")
    shutil.copyfile(SRC / "OFL-newsreader.txt", OUT / "OFL-newsreader.txt")
    shutil.copyfile(SRC / "OFL-noto-serif-tc.txt", OUT / "OFL-noto-serif-tc.txt")
    for p in sorted(OUT.iterdir()):
        print(p.relative_to(ROOT), p.stat().st_size)


if __name__ == "__main__":
    main()
