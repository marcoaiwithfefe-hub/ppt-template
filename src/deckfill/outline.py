"""parse_outline: the D2 outline format into slides plus warnings for lines it could not place."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .errors import OutlineError

MAX_CHARS = 50_000

WS = " \t　"
_HEADING = re.compile(r"^(#+)(?:[ \t　]+(.*))?$")
# Bullet marks of D2. '-', '*' and '1.' / '1)' need a space after them, so '-5%' or '1.5 億'
# stay text; the CJK marks and dots do not.
_BULLET = re.compile(
    r"^(?:[-*](?:[ \t　]+|$)|[•·‧][ \t　]*|\d+[.)](?:[ \t　]+|$)|\d+、[ \t　]*"
    r"|[一二三四五六七八九十百零〇]+、[ \t　]*)"
)
_FENCE = re.compile(r"^(```|~~~)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class Item:
    level: int  # 1 or 2
    text: str


@dataclass(frozen=True)
class OutlineSlide:
    kind: str  # title, content, two, section
    title: str
    subtitle: tuple[str, ...] = ()
    columns: tuple[tuple[Item, ...], ...] = ()
    line: int = 0


@dataclass(frozen=True)
class Warning:
    line: int
    code: str
    text: str


@dataclass(frozen=True)
class Outline:
    title: str
    slides: tuple[OutlineSlide, ...]
    warnings: tuple[Warning, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _indent_level(raw: str) -> int:
    lead = raw[: len(raw) - len(raw.lstrip(WS))]
    if "\t" in lead or "　" in lead or lead.count(" ") >= 2:
        return 2
    return 1


def parse_outline(text: str) -> Outline:
    if len(text) > MAX_CHARS:
        raise OutlineError("too_long", f"{len(text)} characters")
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    warnings: list[Warning] = []
    slides: list[dict] = []
    deck_title: str | None = None
    title_slide: dict | None = None
    cur: dict | None = None  # current ## slide

    def warn(line: int, code: str, txt: str) -> None:
        warnings.append(Warning(line, code, txt))

    for n, raw in enumerate(text.split("\n"), 1):
        raw = _CONTROL.sub("", raw).rstrip(WS + "\v\f")
        stripped = raw.strip(WS)
        if not stripped or _FENCE.match(stripped):
            continue
        m = _HEADING.match(stripped)
        plain = False
        if m and len(m.group(1)) >= 3 and (m.group(2) or "").strip(WS):
            # Not part of D2: read as a plain line so no text is lost.
            warn(n, "heading_level", stripped)
            stripped = m.group(2).strip(WS)
            plain = True
        elif m:
            hashes, body = m.group(1), (m.group(2) or "").strip(WS)
            if len(hashes) == 1 and deck_title is None and not slides:
                if not body:
                    warn(n, "empty_heading", stripped)
                    continue
                deck_title = body
                title_slide = {"kind": "title", "title": body, "subtitle": [], "line": n}
                continue
            if len(hashes) == 1:
                warn(n, "second_title", stripped)
            if not body:
                warn(n, "empty_heading", stripped)
                if len(hashes) >= 3:
                    continue
            cur = {"title": body, "cols": [[], []], "col": 0, "split": False, "line": n}
            slides.append(cur)
            continue
        if stripped == "||":
            if cur is None:
                warn(n, "columns_outside_slide", stripped)
            elif cur["split"]:
                warn(n, "extra_columns", stripped)
            else:
                cur["split"] = True
                cur["col"] = 1
            continue
        level = _indent_level(raw)
        bm = None if plain else _BULLET.match(stripped)
        content = stripped[bm.end():].strip(WS) if bm else stripped
        if bm and not content:
            warn(n, "empty_bullet", stripped)
            continue
        if cur is not None:
            cur["cols"][cur["col"]].append(Item(level, content))
        elif title_slide is not None:
            title_slide["subtitle"].append(content)
        else:
            warn(n, "outside_slide", stripped)

    out: list[OutlineSlide] = []
    if title_slide is not None:
        out.append(OutlineSlide("title", title_slide["title"], tuple(title_slide["subtitle"]), (), title_slide["line"]))
    for s in slides:
        left, right = tuple(s["cols"][0]), tuple(s["cols"][1])
        if s["split"]:
            out.append(OutlineSlide("two", s["title"], (), (left, right), s["line"]))
        elif left:
            out.append(OutlineSlide("content", s["title"], (), (left,), s["line"]))
        else:
            out.append(OutlineSlide("section", s["title"], (), (), s["line"]))
    if deck_title is None:
        if slides:
            deck_title = slides[0]["title"]
            warnings.insert(0, Warning(slides[0]["line"], "no_title", slides[0]["title"]))
        else:
            deck_title = ""
    return Outline(deck_title, tuple(out), tuple(sorted(warnings, key=lambda w: w.line)))
