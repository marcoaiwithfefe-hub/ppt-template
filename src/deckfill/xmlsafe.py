"""Safe XML parsing for untrusted template parts (spec D1b)."""

from lxml import etree

from .errors import TemplateError

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
}
R_NS = NS["r"]


def q(name: str) -> str:
    """'p:sp' -> Clark name."""
    prefix, local = name.split(":")
    return "{%s}%s" % (NS[prefix], local)


def make_parser() -> etree.XMLParser:
    # Entities off, network off, huge_tree off, no DTD loading. remove_blank_text matches
    # the parser python-pptx uses, so canonical comparisons see the same tree.
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=False,
        load_dtd=False,
        remove_blank_text=True,
    )


def parse(data: bytes, where: str = ""):
    try:
        root = etree.fromstring(data, make_parser())
    except (etree.XMLSyntaxError, ValueError) as e:
        raise TemplateError("bad_file", f"xml {where}: {e}") from e
    if root.getroottree().docinfo.doctype:
        # OOXML parts never carry a document type declaration; one here is how entity
        # expansion attacks arrive, so any DOCTYPE is refused.
        raise TemplateError("bad_file", f"doctype in {where}")
    return root
