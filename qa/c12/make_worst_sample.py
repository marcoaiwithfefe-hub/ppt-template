"""C12 sample-route stress inputs (rev 8, C30 "under the caps it meets C12's bars"), at the caps the code enforces
(src/deckfill/sample_plan.py: 40 MB of generated slide XML, 20,000 copied shapes, 20,000 written paragraphs).

- qa/c12/sample-shapes.pptx + sample-shapes-outline.md: fixtures/out/sample-heavy.pptx (one sample of 1,503 shapes)
  filled 13 times: 19,539 copied shapes, just under the shape cap.
- qa/c12/sample-xml.pptx + sample-xml-outline.md: one sample whose slide part is about 4.4 MB (a freeform with a long
  path, under the 5 MB XML part cap), filled 8 times: about 35 MB of generated slide XML, under the 40 MB cap.
The paragraph cap is past what the 50,000-character outline cap allows, so its stress case is the outline worst case.

    .venv/bin/python qa/c12/make_worst_sample.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fixtures"))
from lxml import etree  # noqa: E402

from make_sample_fixtures import M, content_slide, new_prs, q  # noqa: E402

OUT = ROOT / "qa" / "c12"
shutil.copy(ROOT / "fixtures" / "out" / "sample-heavy.pptx", OUT / "sample-shapes.pptx")
(OUT / "sample-shapes-outline.md").write_text("".join(f"## Heavy {i}\n- point {i}\n\n" for i in range(13)), encoding="utf-8")

prs = new_prs()
s = content_slide(prs, 1, (240, 230, 220), "XML heavy sample", "Body")
n = 110_000
pts = "".join(f'<a:lnTo><a:pt x="{(i * 37) % 1000000}" y="{(i * 91) % 1000000}"/></a:lnTo>' for i in range(n))
sp = etree.fromstring(
    '<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<p:nvSpPr><p:cNvPr id="500" name="Path"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
    f'<p:spPr><a:xfrm><a:off x="{8 * M}" y="{5 * M}"/><a:ext cx="{M}" cy="{M}"/></a:xfrm>'
    '<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/>'
    f'<a:pathLst><a:path w="1000000" h="1000000"><a:moveTo><a:pt x="0" y="0"/></a:moveTo>{pts}</a:path></a:pathLst>'
    '</a:custGeom><a:solidFill><a:srgbClr val="808080"/></a:solidFill></p:spPr></p:sp>'
)
s.shapes._spTree.append(sp)
prs.save(OUT / "sample-xml.pptx")
(OUT / "sample-xml-outline.md").write_text("".join(f"## XML {i}\n- point {i}\n\n" for i in range(8)), encoding="utf-8")
import zipfile  # noqa: E402

size = zipfile.ZipFile(OUT / "sample-xml.pptx").getinfo("ppt/slides/slide1.xml").file_size
print("sample-xml slide part", size, "bytes; 8 copies", 8 * size)
