"""plan_deck on the sample-slide route (rev 8, D12 planning, fit and limits).

Each outline slide becomes a copy of one usable sample slide. The planner decides, per output slide, which sample,
which of its boxes take which text, and the size every written run gets, so fill only carries the plan out.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import PlanError, TemplateError
from .outline import Item, Outline, OutlineSlide, Warning
from .plan import CHECK, FITS, MAX_BULLETS, MAX_SLIDES, SPLIT, WARNED, Dest, Plan, PlannedSlide, chunk, cont_title, groups_of, height
from .sample import FOOTER_TYPES, Sample, SBox, box_of, clearing, grow_in_groups, inside

SHRUNK = "shrunk"
SMALL_TEXT = "small_text"  # QA round 1 (QA4): no candidate met the readability bars, or a user pick below them
GROWN = "grown"  # QA round 2 R3: the slide's body box grew into free space (版面調整 on the page)
STEPS = 7  # 100%, 95%, ... 70% (D12 fit)
TITLE_BAR = 4  # QA round 1 Q2: a title destination's written size, percent of the slide height
BODY_BAR = 2  # QA round 1 Q3: a body destination's written size, percent of the slide height
EMU_PER_PT = 12700
MAX_XML = 40 * 1024 * 1024  # generated slide XML, D12 limits
MAX_COPIED_SHAPES = 20_000
MAX_PARAS = 20_000
PARA_MARKUP = 64
SZ_ATTR = len(b' sz="12345"')
_ORDER = {FITS: 0, SHRUNK: 1, SMALL_TEXT: 2, GROWN: 3, SPLIT: 4, WARNED: 5, CHECK: 6}


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
    backing: tuple = ()  # R3: (shape id, grown slide-space box) of a grown body's own backing


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
    grown: tuple | None = None  # R3: the grown body box, slide space, when this candidate grows its body


def _overlap(a: SBox, b: SBox) -> bool:
    return not (a.x + a.cx <= b.x or b.x + b.cx <= a.x)


def title_fill(S: Sample, paras: tuple[str, ...]) -> BoxFill:
    tb = S.box(S.title[0])
    box = S.title_box if len(S.title) > 1 else None
    return fill_box(tb, "title", tuple(Item(1, t) for t in paras), box)


def meets(S: Sample, bf: BoxFill) -> bool:
    """QA round 1 Q2 and Q3: the box's written size after any shrink, level 2 included when the box holds level-2
    paragraphs, is at least the bar for its role (title 4%, every body destination 2% of the slide height). A box
    the plan writes no size on is written at its effective size."""
    sb = S.box(bf.sid)
    bar = TITLE_BAR if bf.role == "title" else BODY_BAR
    sizes = [bf.sizes[0] or sb.lvl1.size]
    if any(lvl == 2 for lvl, _ in bf.paras):
        sizes.append(bf.sizes[1] or sb.lvl2.size)
    # size / 100 pt >= bar / 100 * height / 12700 pt
    return all(sz * EMU_PER_PT >= bar * S.slide[1] for sz in sizes)


def readable(S: Sample, built: "Built") -> bool:
    """QA round 1: every destination of every output slide the candidate makes meets its bar."""
    return all(meets(S, bf) for p in built.parts for bf in p.boxes)


def slot_dest(S: Sample, n: int):
    """The slot group whose size equals the bullet count; ties to the larger total area, then the earlier first slot.
    A group with a rotated or flipped slot is never a destination: it cannot be measured against the bar (C32)."""
    if not (2 <= n <= MAX_BULLETS):
        return None
    cands = [g for g in S.slots if len(g) == n and not any(S.box(s).unmodelled == "rotated or flipped" for s in g)]
    if not cands:
        return None

    def key(g):
        boxes = [S.box(s) for s in g]
        first = boxes[0]
        return (-sum(b.area for b in boxes), first.y, first.x)

    return sorted(cands, key=key)[0]


def slots_for(S: Sample, items: tuple[Item, ...]):
    """The slot group a content slide's level-1 bullets go into, one per slot (D12), with the groups and their box
    fills; None when there is none. QA round 1 Q3: a group is a destination only when every slot holds its bullet,
    children included, at or above the body bar."""
    if not items:
        return None
    groups = groups_of(items)
    slots = slot_dest(S, len(groups))
    if slots is None:
        return None
    fills = [fill_box(S.box(sid), "slot", g) for sid, g in zip(slots, groups)]
    # R7: every slot also fits by the D12 estimate at or above the 70% floor; a slot that would be warned (or that
    # the estimate cannot model) disqualifies its group
    if not all(meets(S, bf) and bf.status in (FITS, SHRUNK) for bf in fills):
        return None
    return slots, groups, fills


def cont_for(S: Sample, title: str) -> str:
    """R2: a continuation slide's title. It keeps the original title with no suffix when the original fits the title
    destination at the floor and the title with （續） or (cont.) does not."""
    suffixed = cont_title(title)
    tb = S.box(S.title[0])
    tbox = S.title_box if len(S.title) > 1 else None
    fits = (lambda t: need_of_box(tb, (Item(1, t),), tbox) < STEPS)
    return title if fits(title) and not fits(suffixed) else suffixed


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


def build(S: Sample, s: OutlineSlide, merge: bool = False) -> Built:
    """Every output slide one outline slide makes on sample S. merge: a two-column slide goes into S's largest body
    box with its columns merged even when S has two column boxes (S2's content variant, code review F4)."""
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
        found = slots_for(S, items)
        if found:
            slots, _, fills = found
            boxes = [title_fill(S, (s.title,))] + fills
            return Built([Part(s.title, tuple(boxes), (items,))], False, False, len(S.bodies) - len(slots))
        body = S.box(S.subtitle)
        chunks, _ = chunk(items, floor_fit(body))
        parts = []
        for p, c in enumerate(chunks):
            title = s.title if p == 0 else cont_for(S, s.title)
            parts.append(Part(title, (title_fill(S, (title,)), fill_box(body, "body", c)), (c,)))
        return Built(parts, False, False, len(S.bodies) - 1)
    # two columns
    pair = None if merge else two_dest(S)
    if pair is None:
        body = S.box(S.subtitle)
        items = s.columns[0] + s.columns[1]
        chunks, _ = chunk(items, floor_fit(body))
        parts = []
        for p, c in enumerate(chunks):
            title = s.title if p == 0 else cont_for(S, s.title)
            parts.append(Part(title, (title_fill(S, (title,)), fill_box(body, "body", c)), (c,)))
        return Built(parts, True, False, len(S.bodies) - 1)
    per_col = [chunk(col, floor_fit(box))[0] for col, box in zip(s.columns, pair)]
    n = max(len(c) for c in per_col)
    parts = []
    for p in range(n):
        title = s.title if p == 0 else cont_for(S, s.title)
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


def needs(S: Sample, s: OutlineSlide, body_box=None, merged: bool = False) -> list[float]:
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
        found = slots_for(S, items)
        if found:
            slots, groups, _ = found
            return out + [need_of_box(S.box(sid), g) for sid, g in zip(slots, groups)]
        return out + [need_of_box(S.box(S.subtitle), items, body_box)]
    pair = None if merged else two_dest(S)
    if pair is None:
        return out + [need_of_box(S.box(S.subtitle), s.columns[0] + s.columns[1])]
    return out + [need_of_box(b, col) for col, b in zip(s.columns, pair) if col]


def rank_key(S: Sample, s: OutlineSlide, built: Built):
    """The ranking QA round 2's R1 leaves after the readability pool, the fewest continuation slides and variety:
    every destination fits at full size, then the smallest shrink, then the fewest body boxes left unused, then the
    ungrown box (R3 ties), then file order. A box over at the floor (warned) or one the estimate cannot model (check)
    does not fit at full size and needs more shrink than any step gives, so it counts as the full 7 steps; a body
    whose unsplit text must split counts the same (decisions.tsv)."""
    boxes = [b for p in built.parts for b in p.boxes]
    worse = any(b.status in (WARNED, CHECK) for b in boxes)
    worst = max(needs(S, s, built.grown, built.merged), default=0.0)
    shrink = float(STEPS) if worse else min(worst, float(STEPS))
    return (worse or worst > 0, shrink, built.unused, built.grown is not None, S.k)


GRID = (64, 36)  # R3 free-space grid, columns by rows
BACKGROUND = 0.60  # a shape covering this share of the slide or more is a declared background and takes no cells
EDGE = 0.04  # cells within this share of a slide edge are taken
TITLE_PAD = 0.02  # the title destination is padded by this share of the slide width
GROWN_MIN = (0.25, 0.15)  # a grown box is used only at this share of the slide width and height or more


def _cells(box, sw: int, sh: int):
    """The cells (r0, r1, c0, c1) a slide-space box overlaps with positive area; None when it misses the slide."""
    x, y, cx, cy = box
    cx, cy = max(cx, 1), max(cy, 1)
    W, H = GRID
    c0, c1 = max((x * W) // sw, 0), min(-((-(x + cx) * W) // sw) - 1, W - 1)
    r0, r1 = max((y * H) // sh, 0), min(-((-(y + cy) * H) // sh) - 1, H - 1)
    return None if c0 > c1 or r0 > r1 else (r0, r1, c0, c1)


def own_backing(S: Sample, body: SBox, fills):
    """R3 own backing: the shapes under the body that pass the R5 backing test, hold at least 80% of the body's area,
    are under 8% of the slide and not a declared background, and hold no other kept destination. Returns the one
    candidate's Leaf, None when there is none, or False when there are two or more (the body does not grow)."""
    sw, sh = S.slide
    area = sw * sh
    order = [lf.sid for lf in S.leaves]
    if body.sid not in order:
        return False
    below = order[: order.index(body.sid)]
    others = [bf.box if bf.role == "title" and bf.box else box_of(S.box(bf.sid)) for bf in fills if bf.sid != body.sid]
    found = []
    for lf in S.leaves:
        if lf.sid not in below or lf.tag != "sp" or lf.text or lf.ph or not lf.rect or lf.qbox is None or lf.hidden:
            continue
        b = lf.qbox
        if b[2] * b[3] >= 0.08 * area or b[2] * b[3] >= BACKGROUND * area:
            continue
        if inside(box_of(body), b) < 0.8 or any(inside(o, b) >= 0.8 for o in others):
            continue
        found.append(lf)
    if len(found) > 1:
        return False
    return found[0] if found else None


def taken_grid(S: Sample, fills, skip: set):
    """R3: which cells of the grid visible content takes on the copy after clearing."""
    sw, sh = S.slide
    W, H = GRID
    area = sw * sh
    taken = [[False] * W for _ in range(H)]

    def mark(box):
        if box is None or box[2] * box[3] >= BACKGROUND * area:
            return
        c = _cells(box, sw, sh)
        if c is None:
            return
        r0, r1, c0, c1 = c
        for r in range(r0, r1 + 1):
            row = taken[r]
            for k in range(c0, c1 + 1):
                row[k] = True

    gone, _ = clearing(S, fills, area)
    frags = set(S.title[1:])
    title = next((bf for bf in fills if bf.role == "title"), None)
    for lf in S.leaves:
        if lf.hidden or lf.sid in gone or lf.sid in frags or lf.sid in skip or lf.ph in FOOTER_TYPES:
            continue
        if title is not None and lf.sid == title.sid:
            continue
        if lf.tag == "sp" and lf.ph and not lf.text:
            continue  # a placeholder with no text is removed (C6)
        mark(lf.occ)
    if title is not None:
        tb = title.box or box_of(S.box(title.sid))
        pad = round(TITLE_PAD * sw)
        mark((tb[0] - pad, tb[1] - pad, tb[2] + 2 * pad, tb[3] + 2 * pad))
    for b in S.fixed:
        mark(b)
    for b in S.footers:
        mark(b)
    for r in range(H):
        for k in range(W):
            if k * sw < EDGE * sw * W or (k + 1) * sw > (1 - EDGE) * sw * W or r * sh < EDGE * sh * H or (r + 1) * sh > (1 - EDGE) * sh * H:
                taken[r][k] = True
    return taken


def largest_rect(taken, need):
    """The largest axis-aligned rectangle of free cells containing the cells need = (r0, r1, c0, c1); ties to the
    top-most, then the left-most. Returns (t, b, l, r) or None when need itself is not free."""
    H, W = len(taken), len(taken[0])
    r0, r1, c0, c1 = need
    if any(taken[r][k] for r in range(r0, r1 + 1) for k in range(c0, c1 + 1)):
        return None
    best = None
    for t in range(r0, -1, -1):
        if any(taken[t][k] for k in range(c0, c1 + 1)):
            break
        ok = [all(not taken[r][k] for r in range(t, r1 + 1)) for k in range(W)]
        for b in range(r1, H):
            if b > r1:
                if any(taken[b][k] for k in range(c0, c1 + 1)):
                    break
                ok = [o and not taken[b][k] for k, o in enumerate(ok)]
            lft = c0
            while lft > 0 and ok[lft - 1]:
                lft -= 1
            rgt = c1
            while rgt < W - 1 and ok[rgt + 1]:
                rgt += 1
            key = (-(b - t + 1) * (rgt - lft + 1), t, lft)
            if best is None or key < best[0]:
                best = (key, (t, b, lft, rgt))
    return best[1]


def grow_build(S: Sample, s: OutlineSlide):
    """R3: the candidate whose largest body box grows into the free space around it, or None. Content slides on the
    single-body path only (never slots, two columns, titles, or a rotated or flipped box). The body's own backing, when
    it has exactly one, grows with it at the same margins and their combined footprint is what must fit the free
    cells. Text is written at the box's effective sizes and fitted by D12 unchanged."""
    items = s.columns[0] if s.columns else ()
    if s.kind != "content" or not items or S.subtitle is None or slots_for(S, items) is not None:
        return None
    body = S.box(S.subtitle)
    if body.unmodelled:
        return None
    sw, sh = S.slide
    W, H = GRID
    title = title_fill(S, (s.title,))
    fills = (title, fill_box(body, "body", items))
    back = own_backing(S, body, fills)
    if back is False:
        return None
    bb = box_of(body)
    if back is not None:
        k = back.qbox
        margins = (bb[0] - k[0], bb[1] - k[1], k[0] + k[2] - bb[0] - bb[2], k[1] + k[3] - bb[1] - bb[3])
    else:
        margins = (0, 0, 0, 0)
    grow = tuple(max(m, 0) for m in margins)  # how far the footprint reaches past the body on each side
    foot = (bb[0] - grow[0], bb[1] - grow[1], bb[2] + grow[0] + grow[2], bb[3] + grow[1] + grow[3])
    need = _cells(foot, sw, sh)
    if need is None:
        return None
    taken = taken_grid(S, fills, {body.sid} | ({back.sid} if back is not None else set()))
    found = largest_rect(taken, need)
    if found is None:
        return None
    t, b, lft, rgt = found
    x0, x1 = -((-lft * sw) // W), ((rgt + 1) * sw) // W
    y0, y1 = -((-t * sh) // H), ((b + 1) * sh) // H
    gbox = (x0 + grow[0], y0 + grow[1], x1 - x0 - grow[0] - grow[2], y1 - y0 - grow[1] - grow[3])
    if gbox[2] < GROWN_MIN[0] * sw or gbox[3] < GROWN_MIN[1] * sh or gbox == bb:
        return None
    moves = [(body.sid, gbox)]
    backing = ()
    if back is not None:
        gk = (gbox[0] - margins[0], gbox[1] - margins[1], gbox[2] + margins[0] + margins[2], gbox[3] + margins[1] + margins[3])
        moves.append((back.sid, gk))
        backing = (back.sid, gk)
    if not grow_in_groups(S, moves):
        return None
    f = body.fit_at(gbox, scaled(body.lvl1.size, STEPS - 1), scaled(body.lvl2.size, STEPS - 1))
    chunks, _ = chunk(items, f)
    parts = []
    for p, c in enumerate(chunks):
        ttl = s.title if p == 0 else cont_for(S, s.title)
        bf = fill_box(body, "body", c, gbox)
        bf = BoxFill(bf.sid, bf.role, bf.paras, bf.sizes, bf.step, bf.status, bf.box, backing)
        parts.append(Part(ttl, (title_fill(S, (ttl,)), bf), (c,)))
    return Built(parts, False, False, len(S.bodies) - 1, gbox)


def compatible(S: Sample, s: OutlineSlide) -> bool:
    if not S.usable:
        return False
    if s.kind in ("content", "two"):
        return bool(S.bodies)
    return True


def flags_of(boxes, split: bool, small: bool = False, grown: bool = False) -> tuple[str, ...]:
    st = {b.status for b in boxes}
    out = []
    if SHRUNK in st:
        out.append(SHRUNK)
    if small:
        out.append(SMALL_TEXT)
    if grown:
        out.append(GROWN)
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
            # QA round 1 Q2: the title sample first; the content and section samples are its fallbacks
            return [[title_sample], [S for S in usable if S is not title_sample and ("content" in S.classes or "section" in S.classes)]]
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
        small = False
        if pick is not None:
            built = build(pick, s)
            # a user pick keeps its sample; when it would need 2 or more continuation slides, its own grown body box
            # (R3) is used instead if it is readable and needs fewer, ties to the ungrown box (decisions.tsv)
            if len(built.parts) - 1 >= 2:
                g = grow_build(pick, s)
                if g is not None and readable(pick, g) and len(g.parts) < len(built.parts):
                    built = g
            small = not readable(pick, built)  # QA4: a user pick below a bar is kept and warned
        else:
            # QA round 2 R1 and R6 with round 3's S1: the candidates are the compatible samples of the slide's class and
            # of its class fallbacks. The readability filter reaches across all of them; inside the readable pool the
            # slide's own class comes first, in D12's fallback order, and a fallback class is used only when no readable
            # candidate of the slide's own class exists. With nothing readable the pool is the first tier with any
            # candidate and the slide is warned small_text (QA4). Inside that tier only the candidates with the fewest
            # continuation slides stay; variety picks among those with its relaxation order, so it never adds a slide;
            # then the ranking.
            tiers_c = [[x for x in t if compatible(x, s)] for t in tiers(s)]
            if not any(tiers_c):
                raise PlanError("incompatible_layout", f"no sample fits slide {s.title!r}")
            seen: dict[str, Sample] = {}
            for t in tiers_c:
                for x in t:
                    seen.setdefault(x.id, x)
            cands = [(x, build(x, s)) for x in seen.values()]
            if s.kind == "two":
                # code review F4: a content-tier sample is compared in its merged form, even one that also has two
                # column boxes (it serves both classes); its two-column form stays a two-tier candidate
                merged = {x.id: build(x, s, merge=True) for x in tiers_c[1]}
                cands += [(x, merged[x.id]) for x in tiers_c[1] if not next(b for y, b in cands if y is x).merged]

            def tier_of(x, b, t):
                ids = {y.id for y in tiers_c[t]}
                if s.kind == "two":  # the two tier holds column builds, the content tier merged ones
                    return x.id in ids and b.merged == (t == 1)
                return x.id in ids

            def pool_of(cands):
                ok = [(x, b) for x, b in cands if readable(x, b)]
                readable_tiers = [[(x, b) for x, b in ok if tier_of(x, b, t)] for t in range(len(tiers_c))]
                if s.kind == "two" and all(readable_tiers[:2]):
                    # S2: two columns yield when they add slides: the content merge wins when its best candidate
                    # needs fewer continuation slides than the best two-column one; equal counts keep the columns
                    if min(len(b.parts) for _, b in readable_tiers[1]) < min(len(b.parts) for _, b in readable_tiers[0]):
                        return readable_tiers[1], False
                for tier in readable_tiers:  # S1: the first class tier that holds a readable candidate
                    if tier:
                        return tier, False
                first = next(t for t in range(len(tiers_c)) if tiers_c[t])
                return [(x, b) for x, b in cands if tier_of(x, b, first)], True

            pool, small = pool_of(cands)
            fewest = min(len(b.parts) for _, b in pool)
            # R3: when the best candidate would still need 2 or more continuation slides, each compatible sample's
            # largest body box is also tried grown into the free space around it, under the same order
            if fewest - 1 >= 2 and s.kind == "content":
                grown = [(x, g) for x, _ in cands for g in [grow_build(x, s)] if g is not None]
                if grown:
                    pool, small = pool_of(cands + grown)
                    fewest = min(len(b.parts) for _, b in pool)
            pool = [(x, b) for x, b in pool if len(b.parts) == fewest]
            pool = ([c for c in pool if c[0].id not in recent[-2:]] or [c for c in pool if c[0].id not in recent[-1:]]
                    or pool)
            pick, built = min(pool, key=lambda c: rank_key(c[0], s, c[1]))
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
            fl = flags_of(part.boxes, split, small, built.grown is not None)
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
