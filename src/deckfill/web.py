"""The page's bridge to deckfill: JSON in, JSON or bytes out (spec D8).

The page calls read, plan and fill as three separate steps, so it can paint its working state
and yield to the browser before each one (D1). The same module runs under CPython in the tests.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from .errors import DeckfillError
from .fill import fill
from .outline import parse_outline
from .cjk import DEFAULT_FACE
from .plan import plan_deck
from .sample_plan import cjk_fired
from .template import read_template

_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def place_overrides(outline, remembered: list[dict]) -> tuple[dict[int, str], list[dict]]:
    """The page remembers each override as the title and kind of its slide and which of the
    slides with that title and kind it was (nth), so an override follows its slide when slides
    are added or removed around it. It also remembers how many slides shared that title and kind
    (count): when that number changed and either side is above one, nth can no longer tell which
    slide it was, so the override is dropped, never moved to a sibling (Codex round 3, F16).
    Returns the overrides by slide index and the remembered overrides whose slide is gone."""
    where: dict[tuple[str, str], list[int]] = {}
    for i, s in enumerate(outline.slides):
        where.setdefault((s.title, s.kind), []).append(i)
    by_index: dict[int, str] = {}
    gone: list[dict] = []
    for r in remembered:
        hits = where.get((r["title"], r["kind"]), [])
        regrouped = r["count"] != len(hits) and max(r["count"], len(hits)) > 1
        if not regrouped and 0 <= r["nth"] < len(hits):
            by_index[hits[r["nth"]]] = r["layout"]
        else:
            gone.append(r)
    return by_index, gone


def groups(outline) -> list[tuple[int, int]]:
    """For each slide, how many earlier slides share its title and kind (nth), and how many
    slides share them in all (count)."""
    keys = [(s.title, s.kind) for s in outline.slides]
    total = Counter(keys)
    seen: Counter = Counter()
    out = []
    for key in keys:
        out.append((seen[key], total[key]))
        seen[key] += 1
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
                # rev 8 (D11): the routes this template offers, the default, and the usable sample slides
                "routes": list(info.routes),
                "route": info.route,
                "samples": [{"id": sm.id, "k": sm.k, "words": sm.words} for sm in info.samples if sm.usable],
            },
            ensure_ascii=False,
        )

    def plan(self, text: str, overrides_json: str = "[]", route: str = "", cjk_face: str = "") -> str:
        """overrides_json: the page's remembered overrides, a list of {title, kind, nth, count, layout, route}.
        route: layout or sample, empty for the template's default (D11). A remembered override made on the other
        route is dropped (switching drops every pick, D11). The reply's overrides are the ones still in use; a
        dropped one comes back as a warning. cjk_face: the face the page picked from its user agent (rev 9 T1), empty
        for the default; the reply's cjk_face names it when any written run got it (step 3's line), else null."""
        self.plan_ = None
        cjk_face = cjk_face or DEFAULT_FACE
        route = route or self.info.route
        remembered = json.loads(overrides_json)
        same = [r for r in remembered if r.get("route", "layout") == route]
        switched = [r for r in remembered if r.get("route", "layout") != route]
        try:
            outline = parse_outline(text)
            by_index, gone = place_overrides(outline, same)
            gone = switched + gone
            plan = plan_deck(self.info, outline, by_index or None, route=route, cjk_face=cjk_face)
        except DeckfillError as e:
            return json.dumps({"ok": False, "code": e.code})
        self.plan_ = plan
        group = groups(outline)
        sources = [
            {
                "line": s.line,
                "title": s.title,
                "kind": s.kind,
                "nth": group[i][0],
                "count": group[i][1],
                "chosen": plan.chosen[i],
                "compatible": list(plan.compatible[i]),
            }
            for i, s in enumerate(outline.slides)
        ]
        # an override the plan dropped (the slide no longer fits it) is not kept either
        # a sample-route pick carries its route; a pick with none is a layout-route pick (rev 7's shape unchanged)
        kept = [
            {"title": s["title"], "kind": s["kind"], "nth": s["nth"], "count": s["count"], "layout": by_index[i],
             **({"route": route} if route != "layout" else {})}
            for i, s in enumerate(sources)
            if i in by_index and s["chosen"] == by_index[i]
        ]
        warnings = [{"line": 0, "code": "layout_gone", "text": r["title"]} for r in gone]
        warnings += [{"line": w.line, "code": w.code, "text": w.text} for w in plan.warnings]
        return json.dumps(
            {
                "ok": True,
                "name": file_name(outline.title),
                "route": route,
                "sources": sources,
                "slides": [
                    {"source": s.source, "part": s.part, "layout": s.layout, "title": s.title, "fit": s.fit, "flags": list(s.flags)}
                    for s in plan.slides
                ],
                "warnings": warnings,
                "overrides": kept,
                "cjk_face": cjk_face if cjk_fired(self.info, plan) else None,
            },
            ensure_ascii=False,
        )

    def fill(self, text: str, overrides_json: str = "[]", route: str = "", cjk_face: str = "") -> bytes:
        """Plan from the outline, overrides and route the page reads at the click, then fill, in one
        call, so a download can never use a plan made from older text (Codex round 1, F1).
        The overrides are placed on that outline the same way plan places them.
        Sets fill_name to the download's name for that same outline."""
        route = route or self.info.route
        outline = parse_outline(text)
        same = [r for r in json.loads(overrides_json) if r.get("route", "layout") == route]
        by_index, _ = place_overrides(outline, same)
        plan = plan_deck(self.info, outline, by_index or None, route=route, cjk_face=cjk_face or DEFAULT_FACE)
        self.fill_name = file_name(outline.title)
        return fill(self.data, self.filename, plan)
