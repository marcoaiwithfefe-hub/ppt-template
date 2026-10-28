"""Load an untrusted .pptx/.potx: size caps (D1b), safe XML, integrity check (D4).

The result is a dict of part name -> bytes plus a clean zip that python-pptx opens.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from .errors import TemplateError
from .xmlsafe import NS, R_NS, parse, q

MAX_FILE = 50 * 1024 * 1024
MAX_MEMBERS = 2000
MAX_TOTAL = 300 * 1024 * 1024
MAX_XML_TOTAL = 30 * 1024 * 1024
MAX_XML_PART = 5 * 1024 * 1024
MAX_RATIO = 100
CHUNK = 1 << 16

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ENCRYPTED_STREAM = "EncryptedPackage".encode("utf-16-le")

CT_PRES = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
CT_TEMPLATE = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
CT_SHOW = "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml"
CT_PRES_MACRO = "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
MAIN_TYPES = {CT_PRES: "pptx", CT_TEMPLATE: "potx", CT_SHOW: "ppsx"}
RT_OFFICE_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
RT_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"

_BAD_URI = re.compile(r"[\x00-\x20\x7f]")


@dataclass
class Package:
    parts: dict[str, bytes]  # zip member name -> bytes, input order kept
    kind: str  # pptx, potx, ppsx
    main: str  # member name of the presentation part

    def zip_bytes(self) -> bytes:
        """A clean zip python-pptx can open. A template's main content type is rewritten to a
        presentation's (D4)."""
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
            for name, data in self.parts.items():
                if name == "[Content_Types].xml" and self.kind != "pptx":
                    data = data.replace(CT_TEMPLATE.encode(), CT_PRES.encode()).replace(
                        CT_SHOW.encode(), CT_PRES.encode()
                    )
                z.writestr(name, data)
        return out.getvalue()


def is_xml_name(name: str) -> bool:
    low = name.lower()
    return low.endswith(".xml") or low.endswith(".rels")


def sniff(data: bytes, filename: str) -> None:
    """Refuse what is plainly not a usable PowerPoint file before unzipping."""
    if len(data) > MAX_FILE:
        raise TemplateError("too_big", f"{len(data)} bytes")
    if data[:8] == OLE_MAGIC:
        # Both old .ppt files and password-protected .pptx files are OLE compound files.
        # A protected file carries an EncryptedPackage stream.
        if ENCRYPTED_STREAM in data:
            raise TemplateError("encrypted")
        raise TemplateError("legacy_ppt")
    if data[:4] not in (b"PK\x03\x04", b"PK\x05\x06"):
        raise TemplateError("not_pptx")


def unzip(data: bytes) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise TemplateError("bad_file", f"zip: {e}") from e
    if len(infos) > MAX_MEMBERS:
        raise TemplateError("too_big", f"{len(infos)} members")
    total = xml_total = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise TemplateError("encrypted", "zip member encrypted")
        total += info.file_size
        if is_xml_name(info.filename):
            xml_total += info.file_size
            if info.file_size > MAX_XML_PART:
                raise TemplateError("too_big", f"xml part {info.filename}")
        if info.file_size and (info.compress_size == 0 or info.file_size / info.compress_size > MAX_RATIO):
            raise TemplateError("too_big", f"ratio {info.filename}")
    if total > MAX_TOTAL or xml_total > MAX_XML_TOTAL:
        raise TemplateError("too_big", "declared size")

    parts: dict[str, bytes] = {}
    total = xml_total = 0
    for info in infos:
        if info.is_dir():
            continue
        is_xml = is_xml_name(info.filename)
        part_cap = MAX_XML_PART if is_xml else MAX_TOTAL
        buf = bytearray()
        try:
            with zf.open(info) as f:
                while True:
                    chunk = f.read(CHUNK)
                    if not chunk:
                        break
                    buf += chunk
                    total += len(chunk)
                    if is_xml:
                        xml_total += len(chunk)
                    # Declared sizes can lie, so the caps also hold on bytes actually read.
                    if len(buf) > part_cap or total > MAX_TOTAL or xml_total > MAX_XML_TOTAL:
                        raise TemplateError("too_big", f"actual size {info.filename}")
        except TemplateError:
            raise
        except RuntimeError as e:
            raise TemplateError("encrypted", str(e)) from e
        except Exception as e:  # BadZipFile (bad CRC, short member), zlib.error, OSError
            raise TemplateError("bad_file", f"{info.filename}: {e}") from e
        if info.filename in parts:
            raise TemplateError("bad_file", f"duplicate member {info.filename}")
        parts[info.filename] = bytes(buf)
    return parts


def rels_name(part: str) -> str:
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def source_of_rels(rels: str) -> str:
    """'ppt/_rels/presentation.xml.rels' -> 'ppt/presentation.xml'; '_rels/.rels' -> ''."""
    d, f = posixpath.split(rels)
    base = posixpath.dirname(d)
    return posixpath.join(base, f[: -len(".rels")]) if f != ".rels" else ""


def resolve_target(source: str, target: str) -> str:
    target = unquote(target)
    if target.startswith("/"):
        path = target[1:]
    else:
        path = posixpath.join(posixpath.dirname(source), target)
    return posixpath.normpath(path).lstrip("/")


@dataclass
class Rel:
    rid: str
    type: str
    target: str  # resolved member name, or the raw URI when external
    external: bool


class Index:
    """Content types and relationships of a package, read with the safe parser."""

    def __init__(self, parts: dict[str, bytes]):
        self.parts = parts
        self.lower = {n.lower(): n for n in parts}
        if "[content_types].xml" not in self.lower:
            raise TemplateError("not_pptx", "no content types")
        ct = parse(parts[self.lower["[content_types].xml"]], "[Content_Types].xml")
        self.defaults = {
            e.get("Extension", "").lower(): e.get("ContentType", "") for e in ct.iter(q("ct:Default"))
        }
        self.overrides = {
            e.get("PartName", "").lstrip("/").lower(): e.get("ContentType", "") for e in ct.iter(q("ct:Override"))
        }
        self._rels: dict[str, dict[str, Rel]] = {}
        self._xml: dict[str, object] = {}

    def xml(self, name: str):
        if name not in self._xml:
            self._xml[name] = parse(self.parts[name], name)
        return self._xml[name]

    def find(self, name: str) -> str | None:
        return name if name in self.parts else self.lower.get(name.lower())

    def content_type(self, name: str) -> str | None:
        ct = self.overrides.get(name.lower())
        if ct:
            return ct
        base = posixpath.basename(name)
        ext = base.rsplit(".", 1)[1].lower() if "." in base else ""  # '.rels' has extension rels
        return self.defaults.get(ext)

    def rels(self, source: str) -> dict[str, Rel]:
        if source in self._rels:
            return self._rels[source]
        out: dict[str, Rel] = {}
        name = self.find(rels_name(source) if source else "_rels/.rels")
        if name:
            root = self.xml(name)
            for e in root.iter(q("pr:Relationship")):
                rid, target = e.get("Id"), e.get("Target")
                if not rid or target is None:
                    raise TemplateError("bad_file", f"relationship without id or target in {name}")
                if rid in out:
                    raise TemplateError("bad_file", f"duplicate rId {rid} in {name}")
                external = e.get("TargetMode") == "External"
                out[rid] = Rel(rid, e.get("Type", ""), target if external else resolve_target(source, target), external)
        self._rels[source] = out
        return out

    def main_part(self) -> str:
        for rel in self.rels("").values():
            if rel.type == RT_OFFICE_DOC and not rel.external:
                found = self.find(rel.target)
                if found:
                    return found
        raise TemplateError("not_pptx", "no office document relationship")


def uri_ok(uri: str) -> bool:
    if not uri or _BAD_URI.search(uri):
        return False
    try:
        urlsplit(uri)
    except ValueError:
        return False
    return True


def check_integrity(parts: dict[str, bytes], idx: Index | None = None) -> list[str]:
    """D4 integrity check. Returns a list of problems; empty means it passes."""
    idx = idx or Index(parts)
    problems: list[str] = []
    for name, data in parts.items():
        if name == "[Content_Types].xml":
            continue
        if idx.content_type(name) is None:
            problems.append(f"no content type: {name}")
        if name.endswith(".rels"):
            continue
        source = name
        rels = idx.rels(source)
        for rel in rels.values():
            if rel.external:
                if not uri_ok(rel.target):
                    problems.append(f"bad external target {rel.target!r} in {name}")
            elif not idx.find(rel.target):
                problems.append(f"missing target {rel.target} from {name}")
        if not is_xml_name(name):
            continue
        root = idx.xml(name)
        for el in root.iter():
            for attr, value in el.attrib.items():
                if attr.startswith("{%s}" % R_NS) and value and value not in rels:
                    problems.append(f"{attr.split('}')[1]}={value} names no relationship in {name}")
    # rels files whose source part does not exist
    for name in parts:
        if name.endswith(".rels"):
            src = source_of_rels(name)
            if src and not idx.find(src):
                problems.append(f"relationships for missing part {src}")
    main = idx.main_part()
    pres = idx.xml(main)
    ids = [e.get("id") for e in pres.iter(q("p:sldId"))]
    if len(ids) != len(set(ids)):
        problems.append("duplicate slide ids")
    return problems


def load(data: bytes, filename: str) -> Package:
    sniff(data, filename)
    parts = unzip(data)
    idx = Index(parts)
    main = idx.main_part()
    ct = idx.content_type(main)
    if ct == CT_PRES_MACRO or ct not in MAIN_TYPES:
        raise TemplateError("not_pptx", f"main content type {ct}")
    # Every XML part goes through the safe parser before python-pptx sees it.
    for name in parts:
        if is_xml_name(name):
            idx.xml(name)
    problems = check_integrity(parts, idx)
    if problems:
        raise TemplateError("bad_file", "; ".join(problems[:5]))
    return Package(parts, MAIN_TYPES[ct], main)
