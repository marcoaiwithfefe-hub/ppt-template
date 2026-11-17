"""Render a deck's slides to PNG with headless LibreOffice for the G0b eye pass (rev 8).

The delivered deck is never touched. A render-only copy names Arial Unicode MS as every run's East Asian face and the
theme's East Asian font, and a private LibreOffice profile holds a copy of the macOS Arial Unicode font, because
headless LibreOffice draws no Chinese from the template's own (absent) fonts. Pages come out of the PDF with pdftoppm.

    .venv/bin/python qa/g0b/lo_render.py <deck.pptx> <out dir> [dpi]
"""
import io
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FACE = "Arial Unicode MS"
deck, out = Path(sys.argv[1]), Path(sys.argv[2])
dpi = sys.argv[3] if len(sys.argv) > 3 else "40"
out.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix="lo-", dir=out))
profile = work / "profile"
(profile / "user" / "fonts").mkdir(parents=True)
shutil.copy(FONT, profile / "user" / "fonts" / "ArialUnicode.ttf")

ea_tag = re.compile(rb"<a:ea typeface=\"[^\"]*\"")


def render_copy(data: bytes) -> bytes:
    zin = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            b = zin.read(info.filename)
            n = info.filename
            if n.endswith(".xml") and (n.startswith("ppt/slides/slide") or n.startswith("ppt/theme/") or
                                       n.startswith("ppt/slideLayouts/") or n.startswith("ppt/slideMasters/")):
                b = ea_tag.sub(b'<a:ea typeface="' + FACE.encode() + b'"', b)
                # runs with no East Asian face of their own get one, so CJK text never falls back to a blank face
                b = re.sub(rb"<a:rPr((?:\s[^>]*)?)/>", lambda m: b"<a:rPr" + m.group(1) + b"><a:ea typeface=\"" + FACE.encode() + b"\"/></a:rPr>", b)
            zout.writestr(info, b)
    return buf.getvalue()


copy = work / (deck.stem + "-render.pptx")
copy.write_bytes(render_copy(deck.read_bytes()))
subprocess.run(["/opt/homebrew/bin/soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--convert-to", "pdf",
                "--outdir", str(work), str(copy)], check=True, capture_output=True, timeout=600)
pdf = work / (copy.stem + ".pdf")
subprocess.run(["/opt/homebrew/bin/pdftoppm", "-r", dpi, "-png", str(pdf), str(out / "slide")], check=True)
print(pdf, "->", out)
