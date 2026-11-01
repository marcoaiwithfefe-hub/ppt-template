"""plan_deck: layout per slide (D3), split or warn on overflow (D5)."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import asdict, dataclass

from .errors import OutlineError, PlanError
from .outline import Item, Outline, OutlineSlide, Warning
from .template import Fit, Layout, Level, TemplateInfo

MAX_SLIDES = 200
MAX_BULLETS = 6
LATIN_EM = 0.55

FITS, SPLIT, WARNED, CHECK = "fits", "split", "warned", "check"
_RANK = {FITS: 0, SPLIT: 1, WARNED: 2, CHECK: 3}


@dataclass(frozen=True)
class Need:
    title: bool
    subtitle: bool
    bodies: int  # 0, 1 or 2


@dataclass(frozen=True)
class Dest:
    """Where each piece of a slide goes on its layout."""

    title: int | None
    subtitle: tuple[str, int] | None  # ("subtitle", idx) or ("body", idx)
    bodies: tuple[int, ...]  # one idx per column; two columns into one body give (idx,)
    merged: bool  # two columns placed in one body (D3 step 4)


@dataclass(frozen=True)
class PlannedSlide:
    source: int  # outline slide index
    part: int  # 0 for the slide itself, 1.. for continuation slides
    layout: str
    kind: str
    title: str
    subtitle: tuple[str, ...]
    columns: tuple[tuple[Item, ...], ...]  # one tuple per destination body
    dest: Dest
    fit: str
    boxes: tuple = ()  # rev 8 sample route: sample_plan.BoxFill per box that receives text
    flags: tuple[str, ...] = ()  # rev 8 sample route: shrunk, split, warned, check (a slide can carry several)


@dataclass(frozen=True)
class Plan:
    outline: Outline
    overrides: tuple[tuple[int, str], ...]
    slides: tuple[PlannedSlide, ...]
    chosen: tuple[str, ...]  # layout id per outline slide
    compatible: tuple[tuple[str, ...], ...]  # compatible layout ids per outline slide
    warnings: tuple[Warning, ...]  # parser warnings first, then planning warnings
    route: str = "layout"  # rev 8: layout or sample (D11)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------------------------
# needs and destinations (D3 step 7)


def need_of(s: OutlineSlide) -> Need:
    if s.kind == "title":
        return Need(True, bool(s.subtitle), 0)
    return Need(True, False, {"content": 1, "two": 2, "section": 0}[s.kind])


def destination(lay: Layout, need: Need) -> Dest | None:
    """None when the layout lacks a destination for some need."""
    if lay.title_idx is None:
        return None
    sub = None
    if need.subtitle:
        if lay.subtitle_idx is not None:
            sub = ("subtitle", lay.subtitle_idx)
        elif lay.main_body is not None:
            sub = ("body", lay.main_body)
        else:
            return None
    bodies: tuple[int, ...] = ()
    merged = False
    if need.bodies == 1:
        if lay.main_body is None:
            return None
        bodies = (lay.main_body,)
    elif need.bodies == 2:
        if lay.columns is not None:
            bodies = lay.columns
        elif lay.main_body is not None:
            bodies, merged = (lay.main_body,), True
        else:
            return None
    return Dest(lay.title_idx, sub, bodies, merged)


def default_layout(info: TemplateInfo, s: OutlineSlide, deck_has_subtitle: bool) -> str:
    """D3 step 4: the class default, then the named fallbacks, then the first compatible."""
    order = {
        "title": ["title", "content"] + ([] if deck_has_subtitle else ["section"]),
        "content": ["content"],
        "two": ["two", "content"],
        "section": ["section", "title", "content"],
    }[s.kind]
    need = need_of(s)
    for cls in order:
        lid = info.default(cls)
        if lid and destination(info.layout(lid), need):
            return lid
    for lay in info.layouts:
        if destination(lay, need):
            return lay.id
    raise PlanError("incompatible_layout", f"no layout fits slide {s.title!r}")


# ---------------------------------------------------------------------------------------------
# fit estimate (D5)


def is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def has_cjk(text: str) -> bool:
    return any(is_cjk(c) for c in text)


def text_lines(text: str, size: int, width: int) -> int:
    """Greedy wrap: CJK glyphs one em and breakable anywhere, other characters 0.55 em and
    broken at spaces."""
    if width <= 0:
        return 10**6
    tokens: list[float] = []
    word = 0.0
    for ch in text:
        if is_cjk(ch):
            if word:
                tokens.append(word)
                word = 0.0
            tokens.append(size)
        elif ch == " ":
            word += LATIN_EM * size
            tokens.append(word)
            word = 0.0
        else:
            word += LATIN_EM * size
    if word:
        tokens.append(word)
    lines, used = 1, 0.0
    for w in tokens:
        if used + w <= width or used == 0 and w <= width:
            used += w
            continue
        if w > width:  # a long word breaks by character, in constant time (Codex round 1, F4)
            if used:
                lines += 1
            k = max(0, math.ceil(w / width) - 1)  # full lines before the last part
            lines += k
            used = w - k * width
            continue
        lines += 1
        used = w
    return lines


def text_width(text: str, size: int) -> float:
    return sum(size if is_cjk(ch) else LATIN_EM * size for ch in text)


def height(items: tuple[Item, ...], fit: Fit) -> int:
    total = 0
    for i, it in enumerate(items):
        lv: Level = fit.levels[min(it.level, 2) - 1]
        if fit.nowrap:
            # rev 8 sample route, wrapping off: one line, and a line wider than the box does not fit at all
            n = 1 if text_width(it.text, lv.size) <= fit.width - lv.margin else 10**6
        else:
            n = text_lines(it.text, lv.size, fit.width - lv.margin)
        total += (lv.before if i else 0) + n * lv.line + lv.after
    return total


def groups_of(items: tuple[Item, ...]) -> list[tuple[Item, ...]]:
    """Level-1 items with their level-2 children."""
    out: list[list[Item]] = []
    for it in items:
        if it.level == 1 or not out:
            out.append([it])
        else:
            out[-1].append(it)
    return [tuple(g) for g in out]


def chunk(items: tuple[Item, ...], fit: Fit | None) -> tuple[list[tuple[Item, ...]], bool]:
    """Split a body's items between level-1 groups. Returns chunks and whether any single group
    alone exceeds the box (a fit warning)."""
    chunks: list[list[Item]] = []
    cur: list[Item] = []
    ngroups = 0
    warned = False
    for g in groups_of(items):
        if fit is not None and height(g, fit) > fit.height:
            warned = True
        if cur and (ngroups >= MAX_BULLETS or (fit is not None and height(tuple(cur) + g, fit) > fit.height)):
            chunks.append(cur)
            cur, ngroups = [], 0
        cur.extend(g)
        ngroups += 1
    if cur or not chunks:
        chunks.append(cur)
    return [tuple(c) for c in chunks], warned


def cont_title(title: str) -> str:
    return title + ("（續）" if has_cjk(title) else " (cont.)")


# ---------------------------------------------------------------------------------------------


def plan_deck(info: TemplateInfo, outline: Outline, overrides: dict[int, str] | None = None, route: str | None = None) -> Plan:
    """route: layout (D3 to D5) or sample (D12); None takes the template's default route (D11)."""
    if not outline.slides:
        raise OutlineError("no_slides")
    route = route or info.route
    if route not in info.routes:
        raise PlanError("route_unavailable", route)
    if route == "sample":
        from .sample_plan import plan_sample

        return plan_sample(info, outline, dict(overrides or {}))
    overrides = dict(overrides or {})
    ids = {lay.id for lay in info.layouts}
    warnings: list[Warning] = list(outline.warnings)
    for k, v in overrides.items():
        if v not in ids:
            raise PlanError("unknown_layout", v)
        if not (0 <= k < len(outline.slides)):
            # its slide is gone: dropped with a warning, no title to name (the page's bridge
            # names it when it drops an override itself)
            warnings.append(Warning(0, "layout_gone", ""))
    deck_has_subtitle = any(s.kind == "title" and s.subtitle for s in outline.slides)
    out: list[PlannedSlide] = []
    chosen: list[str] = []
    compatible: list[tuple[str, ...]] = []
    for i, s in enumerate(outline.slides):
        need = need_of(s)
        compatible.append(tuple(lay.id for lay in info.layouts if destination(lay, need)))
        lid = overrides.get(i)
        dest = destination(info.layout(lid), need) if lid else None
        if lid and dest is None:
            # the slide no longer fits the layout picked for it: its default, with a warning
            warnings.append(Warning(s.line, "layout_dropped", s.title))
        if dest is None:
            lid = default_layout(info, s, deck_has_subtitle)
            dest = destination(info.layout(lid), need)
        lay = info.layout(lid)
        chosen.append(lid)
        if dest.merged:
            warnings.append(Warning(s.line, "columns_merged", s.title))
        if s.kind in ("title", "section"):
            status = FITS
            if dest.subtitle and dest.subtitle[0] == "body" and s.subtitle:
                # the subtitle fills a content body (D3 step 4 fallback or an override): estimate it (F7)
                fit = lay.body(dest.subtitle[1]).fit
                if fit is None:
                    status = CHECK
                    warnings.append(Warning(s.line, "fit_check", s.title))
                elif height(tuple(Item(1, t) for t in s.subtitle), fit) > fit.height:
                    status = WARNED
                    warnings.append(Warning(s.line, "fit_warn", s.title))
            out.append(PlannedSlide(i, 0, lid, s.kind, s.title, s.subtitle, (), dest, status))
            continue
        cols = s.columns
        if dest.merged:
            cols = (cols[0] + cols[1],)
        fits = [lay.body(idx).fit for idx in dest.bodies]
        per_col = [chunk(c, f) for c, f in zip(cols, fits)]
        n = max(len(chunks) for chunks, _ in per_col)
        status = FITS
        if n > 1:
            status = SPLIT
        if any(w for _, w in per_col):
            status = WARNED
            warnings.append(Warning(s.line, "fit_warn", s.title))
        if any(f is None for f in fits):
            status = CHECK
            warnings.append(Warning(s.line, "fit_check", s.title))
        for part in range(n):
            pcols = tuple(chunks[part] if part < len(chunks) else () for chunks, _ in per_col)
            title = s.title if part == 0 else cont_title(s.title)
            out.append(PlannedSlide(i, part, lid, s.kind, title, (), pcols, dest, status))
        if len(out) > MAX_SLIDES:
            raise PlanError("too_many_slides", f"over {MAX_SLIDES}")
    if len(out) > MAX_SLIDES:
        raise PlanError("too_many_slides", f"over {MAX_SLIDES}")
    return Plan(
        outline=outline,
        overrides=tuple(sorted(overrides.items())),
        slides=tuple(out),
        chosen=tuple(chosen),
        compatible=tuple(compatible),
        warnings=tuple(warnings),
    )
