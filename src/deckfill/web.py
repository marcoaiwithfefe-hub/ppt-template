"""The page's bridge to deckfill: JSON in, JSON or bytes out (spec D8).

The page calls read, plan and fill as three separate steps, so it can paint its working state
and yield to the browser before each one (D1). The same module runs under CPython in the tests.
"""

from __future__ import annotations

import json
import re

from .errors import DeckfillError
from .fill import fill
from .outline import parse_outline
from .plan import plan_deck
from .template import read_template

_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def place_overrides(outline, remembered: list[dict]) -> tuple[dict[int, str], list[dict]]:
    """The page remembers each override as the title and kind of its slide and which of the
    slides with that title and kind it was (nth), so an override follows its slide when slides
    are added or removed around it. Returns the overrides by slide index and the remembered
    overrides whose slide is gone."""
    where: dict[tuple[str, str], list[int]] = {}
    for i, s in enumerate(outline.slides):
        where.setdefault((s.title, s.kind), []).append(i)
    by_index: dict[int, str] = {}
    gone: list[dict] = []
    for r in remembered:
        hits = where.get((r["title"], r["kind"]), [])
        if 0 <= r["nth"] < len(hits):
            by_index[hits[r["nth"]]] = r["layout"]
        else:
            gone.append(r)
    return by_index, gone


def nths(outline) -> list[int]:
    """For each slide, how many earlier slides share its title and kind."""
    seen: dict[tuple[str, str], int] = {}
    out = []
    for s in outline.slides:
        key = (s.title, s.kind)
        out.append(seen.get(key, 0))
        seen[key] = out[-1] + 1
    return out


def file_name(title: str) -> str:
    """The download's name without extension: the deck title, made safe for Windows."""
    name = " ".join(_UNSAFE_NAME.sub(" ", title).split()).strip(".")
    return name[:80].strip() or "簡報"


class Session:
    def __init__(self) -> None:
        self.data: bytes | None = None
        self.filename = ""
        self.info = None
        self.plan_ = None
        self.fill_name = ""

    def read(self, data: bytes, filename: str) -> str:
        self.data, self.filename, self.info, self.plan_ = None, "", None, None
        try:
            info = read_template(bytes(data), filename)
        except DeckfillError as e:
            return json.dumps({"ok": False, "code": e.code})
        self.data, self.filename, self.info = bytes(data), filename, info
        return json.dumps(
            {
                "ok": True,
                "masters": len(info.masters),
                "layouts": [
                    {"id": lay.id, "name": lay.name, "master": lay.master, "cls": lay.cls} for lay in info.layouts
                ],
                "defaults": {cls: lid for cls, lid in info.defaults if lid},
            },
            ensure_ascii=False,
        )

    def plan(self, text: str, overrides_json: str = "[]") -> str:
        """overrides_json: the page's remembered overrides, a list of {title, kind, nth, layout}.
        The reply's overrides are the ones still in use; a dropped one comes back as a warning."""
        self.plan_ = None
        remembered = json.loads(overrides_json)
        try:
            outline = parse_outline(text)
            by_index, gone = place_overrides(outline, remembered)
            plan = plan_deck(self.info, outline, by_index or None)
        except DeckfillError as e:
            return json.dumps({"ok": False, "code": e.code})
        self.plan_ = plan
        nth = nths(outline)
        sources = [
            {
                "line": s.line,
                "title": s.title,
                "kind": s.kind,
                "nth": nth[i],
                "chosen": plan.chosen[i],
                "compatible": list(plan.compatible[i]),
            }
            for i, s in enumerate(outline.slides)
        ]
        # an override the plan dropped (the slide no longer fits it) is not kept either
        kept = [
            {"title": s["title"], "kind": s["kind"], "nth": s["nth"], "layout": by_index[i]}
            for i, s in enumerate(sources)
            if i in by_index and s["chosen"] == by_index[i]
        ]
        warnings = [{"line": 0, "code": "layout_gone", "text": r["title"]} for r in gone]
        warnings += [{"line": w.line, "code": w.code, "text": w.text} for w in plan.warnings]
        return json.dumps(
            {
                "ok": True,
                "name": file_name(outline.title),
                "sources": sources,
                "slides": [
                    {"source": s.source, "part": s.part, "layout": s.layout, "title": s.title, "fit": s.fit}
                    for s in plan.slides
                ],
                "warnings": warnings,
                "overrides": kept,
            },
            ensure_ascii=False,
        )

    def fill(self, text: str, overrides_json: str = "[]") -> bytes:
        """Plan from the outline and overrides the page reads at the click, then fill, in one
        call, so a download can never use a plan made from older text (Codex round 1, F1).
        The overrides are placed on that outline the same way plan places them.
        Sets fill_name to the download's name for that same outline."""
        outline = parse_outline(text)
        by_index, _ = place_overrides(outline, json.loads(overrides_json))
        plan = plan_deck(self.info, outline, by_index or None)
        self.fill_name = file_name(outline.title)
        return fill(self.data, self.filename, plan)
