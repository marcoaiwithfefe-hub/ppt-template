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

    def plan(self, text: str, overrides_json: str = "{}") -> str:
        self.plan_ = None
        overrides = {int(k): v for k, v in json.loads(overrides_json).items()}
        try:
            outline = parse_outline(text)
            plan = plan_deck(self.info, outline, overrides or None)
        except DeckfillError as e:
            return json.dumps({"ok": False, "code": e.code})
        self.plan_ = plan
        sources = [
            {"line": s.line, "title": s.title, "chosen": plan.chosen[i], "compatible": list(plan.compatible[i])}
            for i, s in enumerate(outline.slides)
        ]
        return json.dumps(
            {
                "ok": True,
                "name": file_name(outline.title),
                "sources": sources,
                "slides": [
                    {"source": s.source, "part": s.part, "layout": s.layout, "title": s.title, "fit": s.fit}
                    for s in plan.slides
                ],
                "warnings": [{"line": w.line, "code": w.code, "text": w.text} for w in plan.warnings],
            },
            ensure_ascii=False,
        )

    def fill(self, text: str, overrides_json: str = "{}") -> bytes:
        """Plan from the outline and overrides the page reads at the click, then fill, in one
        call, so a download can never use a plan made from older text (Codex round 1, F1).
        Sets fill_name to the download's name for that same outline."""
        overrides = {int(k): v for k, v in json.loads(overrides_json).items()}
        outline = parse_outline(text)
        plan = plan_deck(self.info, outline, overrides or None)
        self.fill_name = file_name(outline.title)
        return fill(self.data, self.filename, plan)
