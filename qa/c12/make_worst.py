"""C12 worst case: the largest template and outline the D1b caps allow.

Template, from wui-tung.pptx, at the rev 5 caps: 2,000 members, a file just under 100 MB, just
under 150 MB uncompressed, 30 MB of XML with parts just under 5 MB, every member under the 100:1
ratio. Both size caps bind at once: random filler fills the file, compressible media fills the
uncompressed total. The big parts are reachable from the master, so python-pptx loads, copies
and saves them. Outline: 50,000 characters that plan to
200 slides. Writes qa/c12/worst-case.pptx (gitignored) and qa/c12/worst-outline.md.

Run: .venv/bin/python qa/c12/make_worst.py
"""

from __future__ import annotations

import io
import os
import random
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from deckfill import package  # noqa: E402

OUT = ROOT / "qa" / "c12"
MB = 1024 * 1024
RT_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
RT_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def compressible(size: int, ratio: float) -> bytes:
    """Bytes that deflate at roughly `ratio`:1 (zeros with a sprinkle of random bytes)."""
    rnd = random.Random(7)
    step = max(2, int(ratio * 0.62))
    buf = bytearray(size)
    for i in range(0, size, step):
        buf[i] = rnd.randrange(256)
    return bytes(buf)


def xml_part(size: int, seed: int) -> bytes:
    rnd = random.Random(seed)
    head = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<root xmlns="urn:c12">'
    tail = b"</root>"
    items, n = [], len(head) + len(tail)
    while n < size - 200:
        text = "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(120))
        item = f'<i a="{rnd.randrange(10**9)}">{text}</i>'.encode()
        items.append(item)
        n += len(item)
    return head + b"".join(items) + tail


def main() -> None:
    src = ROOT / "fixtures" / "out" / "wui-tung.pptx"
    with zipfile.ZipFile(src) as z:
        base = {n: z.read(n) for n in z.namelist()}
    base_xml = sum(len(v) for n, v in base.items() if package.is_xml_name(n))

    xml_each = package.MAX_XML_PART - 64 * 1024
    left = package.MAX_XML_TOTAL - base_xml - 256 * 1024
    sizes = [xml_each] * int(left // xml_each) + [int(left % xml_each)]
    big_xml = {f"customXml/c12-{k}.xml": xml_part(n, k) for k, n in enumerate(sizes) if n > 1024}

    # media names are fixed now; their sizes are solved below, once the rest is zipped
    n_media = 2
    media = {f"ppt/media/c12-{k}.bin": b"" for k in range(n_media)}

    rels_name = "ppt/slideMasters/_rels/slideMaster1.xml.rels"
    rels = base[rels_name].decode()
    extra = "".join(
        f'<Relationship Id="rIdC12x{k}" Type="{RT_CUSTOM}" Target="../../{n}"/>' for k, n in enumerate(big_xml)
    ) + "".join(
        f'<Relationship Id="rIdC12m{k}" Type="{RT_IMAGE}" Target="../media/{Path(n).name}"/>'
        for k, n in enumerate([*media, "ppt/media/c12-filler.bin"])
    )
    base[rels_name] = rels.replace("</Relationships>", extra + "</Relationships>").encode()
    ct = base["[Content_Types].xml"].decode()
    if 'Extension="bin"' not in ct:
        ct = ct.replace("<Default ", '<Default Extension="bin" ContentType="application/octet-stream"/><Default ', 1)
    base["[Content_Types].xml"] = ct.encode()

    members = dict(base) | big_xml
    # small members up to the member cap (the media and the filler take the last three)
    n_small = package.MAX_MEMBERS - len(members) - n_media - 1
    for k in range(n_small):
        members[f"ppt/c12-small/{k}.bin"] = os.urandom(16)
    path = OUT / "worst-case.pptx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, v in members.items():
            z.writestr(n, v)
    size_now = path.stat().st_size
    total_now = sum(len(v) for v in members.values())

    # Solve filler F (random: F in the file, F in the total) and media M (ratio r: M / r in the
    # file, M in the total) so that both caps are reached, with a margin under each:
    #   total_now + F + M = MAX_TOTAL - margin,  size_now + F + M / r = MAX_FILE - margin
    sample = compressible(4 * MB, 90)
    r = len(sample) / len(zlib.compress(sample, 6))
    assert r < package.MAX_RATIO, r
    margin = 512 * 1024
    t_left = package.MAX_TOTAL - margin - total_now
    f_left = package.MAX_FILE - margin - size_now
    m = max(0, int((t_left - f_left) / (1 - 1 / r)))
    f = max(0, t_left - m)
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as z:
        for name in media:
            z.writestr(name, compressible(m // n_media, 90))
        z.writestr("ppt/media/c12-filler.bin", os.urandom(f))

    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
    print(
        "worst-case.pptx", path.stat().st_size / MB, "MB file;", len(infos), "members;",
        round(sum(i.file_size for i in infos) / MB, 1), "MB uncompressed;",
        round(sum(i.file_size for i in infos if package.is_xml_name(i.filename)) / MB, 1), "MB XML;",
        "max ratio", round(max(i.file_size / max(i.compress_size, 1) for i in infos), 1),
    )

    # outline: as many 12-bullet slides of 30 glyphs as plan to 200 slides or fewer on this template
    from deckfill import PlanError, parse_outline, plan_deck, read_template

    info = read_template(src.read_bytes(), "wui-tung.pptx")
    rnd = random.Random(3)
    glyphs = "營運部門客戶服務送貨準時率倉存周轉跨境路線科技預算培訓司機車隊報告檢討計劃目標"
    slides = [[("- " + "".join(rnd.choice(glyphs) for _ in range(30))) for _ in range(12)] for _ in range(120)]
    for n in range(120, 0, -1):
        lines = ["# C12 最壞情況", "測試用"]
        for k in range(n):
            lines += [f"## 第 {k + 1} 項"] + slides[k]
        text = "\n".join(lines) + "\n"
        if len(text) > 50_000:
            continue
        try:
            planned = len(plan_deck(info, parse_outline(text)).slides)
        except PlanError:
            continue
        break
    (OUT / "worst-outline.md").write_text(text, encoding="utf-8")
    print("worst-outline.md", n, "outline slides,", planned, "planned slides,", end=" ")
    print("worst-outline.md", len(text), "characters")


if __name__ == "__main__":
    main()
