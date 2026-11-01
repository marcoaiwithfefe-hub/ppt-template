"""plan_deck on the sample-slide route (rev 8, D12 planning, fit and limits).

Each outline slide becomes a copy of one usable sample slide. The planner decides, per output slide, which sample,
which of its boxes take which text, and the size every written run gets, so fill only carries the plan out.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import PlanError, TemplateError
from .outline import Item, Outline, OutlineSlide, Warning
from .plan import CHECK, FITS, MAX_BULLETS, MAX_SLIDES, SPLIT, WARNED, Dest, Plan, PlannedSlide, chunk, cont_title, groups_of, height
from .sample import Sample, SBox

SHRUNK = "shrunk"
STEPS = 7  # 100%, 95%, ... 70% (D12 fit)
MAX_XML = 40 * 1024 * 1024  # generated slide XML, D12 limits
MAX_COPIED_SHAPES = 20_000
MAX_PARAS = 20_000
PARA_MARKUP = 64
SZ_ATTR = len(b' sz="12345"')
_ORDER = {FITS: 0, SHRUNK: 1, SPLIT: 2, WARNED: 3, CHECK: 4}


@dataclass(frozen=True)
class BoxFill:
    """What one box of the copy receives: its paragraphs (level, text), the explicit size written on level-1 and
    level-2 runs (0 when the box fits at full size and no size is written), the shrink step, the fit status, and the
    widened slide-space box of a title whose fragments are joined."""

    sid: int
    role: str  # title, subtitle, body, slot
    paras: tuple[tuple[int, str], ...]
    sizes: tuple[int, int]
    step: int
    status: str  # fits, shrunk, warned, check
    box: tuple[int, int, int, int] | None = None


def scaled(eff: int, k: int) -> int:
    """Step k of the shrink: eff scaled by (100 - 5k)%, rounded down to a multiple of 50, never below the smallest
    multiple of 50 at or above 70% of eff (D12 fit). Step 0 is the effective size itself."""
    if k == 0:
        return eff
    down = eff * (100 - 5 * k) // 5000 * 50
    floor = (eff * 70 + 4999) // 5000 * 50
    return max(down, floor)


def place(sb: SBox, items: tuple[Item, ...], box=None) -> tuple[int, str, tuple[int, int]]:
    """The smallest shrink step at which the items fit the box by the D5 estimate."""
    if sb.unmodelled:
        return 0, CHECK, (0, 0)
    for k in range(STEPS):
        s1, s2 = scaled(sb.lvl1.size, k), scaled(sb.lvl2.size, k)
        f = sb.fit_at(box, s1, s2)
        if height(items, f) <= f.height:
            return k, (FITS if k == 0 else SHRUNK), ((s1, s2) if k else (0, 0))
    k = STEPS - 1
    return k, WARNED, (scaled(sb.lvl1.size, k), scaled(sb.lvl2.size, k))


def floor_fit(sb: SBox):
    """The box at the 70% floor: splits are computed against it (D12 splits)."""
    return sb.fit_at(None, scaled(sb.lvl1.size, STEPS - 1), scaled(sb.lvl2.size, STEPS - 1))


def fill_box(sb: SBox, role: str, items: tuple[Item, ...], box=None) -> BoxFill:
    k, status, sizes = place(sb, items, box)
    return BoxFill(sb.sid, role, tuple((it.level, it.text) for it in items), sizes, k, status, box)


@dataclass
class Part:
    title: str
    boxes: tuple[BoxFill, ...]
    columns: tuple[tuple[Item, ...], ...]


@dataclass
class Built:
    parts: list[Part]
    merged: bool
    subtitle_in_title: bool
    unused: int  # body boxes left without text


def _overlap(a: SBox, b: SBox) -> bool:
    return not (a.x + a.cx <= b.x or b.x + b.cx <= a.x)


def title_fill(S: Sample, paras: tuple[str, ...]) -> BoxFill:
    tb = S.box(S.title[0])
    box = S.title_box if len(S.title) > 1 else None
    return fill_box(tb, "title", tuple(Item(1, t) for t in paras), box)


def slot_dest(S: Sample, n: int):
    """The slot group whose size equals the bullet count; ties to the larger total area, then the earlier first slot."""
    if not (2 <= n <= MAX_BULLETS):
        return None
    cands = [g for g in S.slots if len(g) == n]
    if not cands:
        return None

    def key(g):
        boxes = [S.box(s) for s in g]
        first = boxes[0]
        return (-sum(b.area for b in boxes), first.y, first.x)

    return sorted(cands, key=key)[0]


def two_dest(S: Sample):
    """Two non-overlapping body boxes, left first: a 2-slot group, else the slide's only two body boxes."""
    pairs = []
    for g in S.slots:
        if len(g) == 2:
            a, b = (S.box(s) for s in g)
            if not _overlap(a, b):
                pairs.append((a, b))
    if pairs:
        a, b = sorted(pairs, key=lambda p: (-(p[0].area + p[1].area), min(p[0].y, p[1].y), min(p[0].x, p[1].x)))[0]
        return tuple(sorted((a, b), key=lambda x: x.x))
    if len(S.bodies) == 2:
        a, b = (S.box(s) for s in S.bodies)
        if not _overlap(a, b):
            return tuple(sorted((a, b), key=lambda x: x.x))
    return None


def build(S: Sample, s: OutlineSlide) -> Built:
    """Every output slide one outline slide makes on sample S."""
    used: set[int] = set()
    if s.kind == "title":
        paras = (s.title,)
        boxes = []
        sit = False
        if s.subtitle:
            if S.subtitle is not None:
                sub = S.box(S.subtitle)
                boxes.append(fill_box(sub, "subtitle", tuple(Item(1, t) for t in s.subtitle)))
                used.add(sub.sid)
            else:
                paras = (s.title,) + tuple(s.subtitle)
                sit = True
        boxes.insert(0, title_fill(S, paras))
        return Built([Part(s.title, tuple(boxes), ())], False, sit, len([b for b in S.bodies if b not in used]))
    if s.kind == "section":
        return Built([Part(s.title, (title_fill(S, (s.title,)),), ())], False, False, len(S.bodies))
    if s.kind == "content":
        items = s.columns[0] if s.columns else ()
        groups = groups_of(items)
        slots = slot_dest(S, len(groups)) if items else None
        if slots:
            boxes = [title_fill(S, (s.title,))]
            for sid, g in zip(slots, groups):
                boxes.append(fill_box(S.box(sid), "slot", g))
            return Built([Part(s.title, tuple(boxes), (items,))], False, False, len(S.bodies) - len(slots))
        body = S.box(S.subtitle)
        chunks, _ = chunk(items, floor_fit(body))
        parts = []
        for p, c in enumerate(chunks):
            title = s.title if p == 0 else cont_title(s.title)
            parts.append(Part(title, (title_fill(S, (title,)), fill_box(body, "body", c)), (c,)))
        return Built(parts, False, False, len(S.bodies) - 1)
    # two columns
    pair = two_dest(S)
    if pair is None:
        body = S.box(S.subtitle)
        items = s.columns[0] + s.columns[1]
        chunks, _ = chunk(items, floor_fit(body))
        parts = []
        for p, c in enumerate(chunks):
            title = s.title if p == 0 else cont_title(s.title)
            parts.append(Part(title, (title_fill(S, (title,)), fill_box(body, "body", c)), (c,)))
        return Built(parts, True, False, len(S.bodies) - 1)
    per_col = [chunk(col, floor_fit(box))[0] for col, box in zip(s.columns, pair)]
    n = max(len(c) for c in per_col)
    parts = []
    for p in range(n):
        title = s.title if p == 0 else cont_title(s.title)
        boxes = [title_fill(S, (title,))]
        cols = []
        for chunks, box in zip(per_col, pair):
            c = chunks[p] if p < len(chunks) else ()
            cols.append(c)
            if c:
                boxes.append(fill_box(box, "body", c))
        parts.append(Part(title, tuple(boxes), tuple(cols)))
    return Built(parts, False, False, len(S.bodies) - 2)


def need_of_box(sb: SBox, items: tuple[Item, ...], box=None) -> float:
    """How much shrink a box needs to hold all its text unsplit: the step (0 to 6) at which it fits; past the floor,
    7 plus how many times over the floor height the text runs; a box the estimate cannot model counts as 7."""
    if sb.unmodelled:
        return float(STEPS)
    for k in range(STEPS):
        f = sb.fit_at(box, scaled(sb.lvl1.size, k), scaled(sb.lvl2.size, k))
        if height(items, f) <= f.height:
            return float(k)
    f = sb.fit_at(box, scaled(sb.lvl1.size, STEPS - 1), scaled(sb.lvl2.size, STEPS - 1))
    return STEPS + height(items, f) / max(f.height, 1)


def needs(S: Sample, s: OutlineSlide) -> list[float]:
    """The shrink each destination needs for the outline slide's whole text, before any split (the ranking reads
    D12's "every destination fits at full size" against the slide's text, so a candidate that must split ranks
    by how far over the floor it runs: decisions.tsv)."""
    tb = S.box(S.title[0])
    tbox = S.title_box if len(S.title) > 1 else None
    if s.kind == "title":
        if s.subtitle and S.subtitle is not None:
            return [need_of_box(tb, (Item(1, s.title),), tbox), need_of_box(S.box(S.subtitle), tuple(Item(1, t) for t in s.subtitle))]
        return [need_of_box(tb, tuple(Item(1, t) for t in (s.title,) + tuple(s.subtitle)), tbox)]
    out = [need_of_box(tb, (Item(1, s.title),), tbox)]
    if s.kind == "section":
        return out
    if s.kind == "content":
        items = s.columns[0] if s.columns else ()
        groups = groups_of(items)
        slots = slot_dest(S, len(groups)) if items else None
        if slots:
            return out + [need_of_box(S.box(sid), g) for sid, g in zip(slots, groups)]
        return out + [need_of_box(S.box(S.subtitle), items)]
    pair = two_dest(S)
    if pair is None:
        return out + [need_of_box(S.box(S.subtitle), s.columns[0] + s.columns[1])]
    return out + [need_of_box(b, col) for col, b in zip(s.columns, pair) if col]


def rank_key(S: Sample, s: OutlineSlide, built: Built):
    """D12 ranking: every destination fits at full size, then the smallest shrink needed, then the fewest body boxes
    left unused, then file order. A box still over at the floor after any split (a title, subtitle, slot or single
    long bullet, continuation titles included) needs more shrink than any step gives, so candidates are compared on
    those boxes first, then on boxes the estimate cannot model, then on the shrink the slide's unsplit text needs
    (decisions.tsv)."""
    boxes = [b for p in built.parts for b in p.boxes]
    warned = sum(1 for b in boxes if b.status == WARNED)
    check = sum(1 for b in boxes if b.status == CHECK)
    n = needs(S, s)
    worst = max(n, default=0.0)
    return (warned, check, worst > 0, worst, built.unused, S.k)


def compatible(S: Sample, s: OutlineSlide) -> bool:
    if not S.usable:
        return False
    if s.kind in ("content", "two"):
        return bool(S.bodies)
    return True


def flags_of(boxes, split: bool) -> tuple[str, ...]:
    st = {b.status for b in boxes}
    out = []
    if SHRUNK in st:
        out.append(SHRUNK)
    if split:
        out.append(SPLIT)
    if WARNED in st:
        out.append(WARNED)
    if CHECK in st:
        out.append(CHECK)
    return tuple(out)


def plan_sample(info, outline: Outline, overrides: dict[int, str]) -> Plan:
    samples = {S.id: S for S in info.samples}
    usable = [S for S in info.samples if S.usable]
    title_sample = usable[0]
    warnings: list[Warning] = list(outline.warnings)
    for k, v in overrides.items():
        if v not in samples:
            raise PlanError("unknown_layout", v)
        if not (0 <= k < len(outline.slides)):
            warnings.append(Warning(0, "layout_gone", ""))

    def of_class(cls):
        return [S for S in usable if cls in S.classes]

    def tiers(s: OutlineSlide):
        if s.kind == "title":
            return [[title_sample]]
        if s.kind == "section":
            return [of_class("section"), [title_sample], of_class("content")]
        if s.kind == "content":
            return [of_class("content")]
        return [of_class("two"), of_class("content")]

    out: list[PlannedSlide] = []
    chosen: list[str] = []
    compat: list[tuple[str, ...]] = []
    recent: list[str] = []
    for i, s in enumerate(outline.slides):
        compat.append(tuple(S.id for S in usable if compatible(S, s)))
        pick = None
        lid = overrides.get(i)
        if lid:
            S = samples[lid]
            if compatible(S, s):
                pick = S
            else:
                warnings.append(Warning(s.line, "layout_dropped", s.title))
        if pick is not None:
            built = build(pick, s)
        else:
            tier = next((t for t in ([x for x in t if compatible(x, s)] for t in tiers(s)) if t), None)
            if tier is None:
                raise PlanError("incompatible_layout", f"no sample fits slide {s.title!r}")
            pool = [S for S in tier if S.id not in recent[-2:]] or [S for S in tier if S.id not in recent[-1:]] or tier
            cands = [(rank_key(S, s, b), S, b) for S, b in ((S, build(S, s)) for S in pool)]
            _, pick, built = min(cands, key=lambda c: c[0])
        chosen.append(pick.id)
        recent.append(pick.id)
        if built.merged:
            warnings.append(Warning(s.line, "columns_merged", s.title))
        if built.subtitle_in_title:
            warnings.append(Warning(s.line, "subtitle_in_title", s.title))
        split = len(built.parts) > 1
        all_boxes = [b for p in built.parts for b in p.boxes]
        if any(b.status == WARNED for b in all_boxes):
            warnings.append(Warning(s.line, "fit_warn", s.title))
        if any(b.status == CHECK for b in all_boxes):
            warnings.append(Warning(s.line, "fit_check", s.title))
        for p, part in enumerate(built.parts):
            fl = flags_of(part.boxes, split)
            fit = max(fl, key=lambda f: _ORDER[f]) if fl else FITS
            out.append(PlannedSlide(i, p, pick.id, s.kind, part.title, s.subtitle if s.kind == "title" else (),
                                    part.columns, Dest(None, None, (), False), fit, part.boxes, fl))
            if len(out) > MAX_SLIDES:
                raise PlanError("too_many_slides", f"over {MAX_SLIDES}")
    check_limits(samples, out)
    return Plan(outline=outline, overrides=tuple(sorted(overrides.items())), slides=tuple(out), chosen=tuple(chosen),
                compatible=tuple(compat), warnings=tuple(warnings), route="sample")


def plan_bytes(samples, slides) -> tuple[int, int, int]:
    """D12 limits: the generated slide XML (each copy's source part, plus per written paragraph the exact a:pPr and
    a:rPr it carries, its UTF-8 text and the markup, plus the footers), copied shapes and written paragraphs."""
    total = shapes = paras = 0
    for ps in slides:
        S = samples[ps.layout]
        total += S.nbytes + S.footer_bytes
        shapes += S.nshapes
        for bf in ps.boxes:
            sb = S.box(bf.sid)
            for lvl, text in bf.paras:
                total += (sb.ppr1 if lvl == 1 else sb.ppr2) + sb.rpr + (SZ_ATTR if bf.sizes[0] else 0)
                total += len(text.encode("utf-8")) + PARA_MARKUP
                paras += 1
    return total, shapes, paras


def check_limits(samples, slides) -> None:
    total, shapes, paras = plan_bytes(samples, slides)
    if total > MAX_XML or shapes > MAX_COPIED_SHAPES or paras > MAX_PARAS:
        raise TemplateError("too_big", f"sample route: {total} bytes, {shapes} shapes, {paras} paragraphs")
