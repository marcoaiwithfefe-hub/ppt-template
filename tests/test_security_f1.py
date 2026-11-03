"""Security audit F1 (2026-11-04): a crafted deck whose one slide holds 1,600 stacked text boxes (distinct sizes under
the title, 43 KB, inside every D1b cap) froze the page's main thread at template read (160.8 s in the browser, 41.6 s in
CPython at 28f22da) through read_pairs' cubic search and clearing's per-leaf scan. The deck is built here in memory, the
way the audit's generator builds it."""

import io
import time

from pptx import Presentation
from pptx.util import Inches

from deckfill import fill, parse_outline, plan_deck, read_template
from deckfill import template
from deckfill.sample import MAX_PAIR_BODIES, MAX_SAMPLE_TEXT_BOXES, read_pairs


def crafted(n: int) -> bytes:
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
    s.shapes.title.text = "Quarterly review"
    for i in range(n):
        tb = s.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(1))
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = "body text here"
        r._r.get_or_add_rPr().set("sz", str(1000 + n - i))  # distinct sizes, all under the title
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def timed_read(data: bytes):
    template._cache.clear()  # read_template caches by bytes
    t = time.perf_counter()
    info = read_template(data, "crafted.pptx")
    return info, time.perf_counter() - t


def test_f1_crafted_1600_box_slide_reads_fast_and_is_unusable():
    info, dt = timed_read(crafted(1600))
    assert dt < 2.0, f"read took {dt:.1f} s"
    S = info.samples[0]
    assert not S.usable and S.reason == "too_big"


def test_f1_slide_at_the_text_box_cap_reads_plans_and_fills_fast():
    data = crafted(MAX_SAMPLE_TEXT_BOXES - 1)  # the title box makes MAX_SAMPLE_TEXT_BOXES: still read
    info, dt = timed_read(data)
    assert info.samples[0].usable and info.samples[0].pair_groups == ()
    t = time.perf_counter()
    plan = plan_deck(info, parse_outline("# Deck\nsub\n\n## Points\n- a\n- b\n- c\n"), None, route="sample")
    out = fill(data, "crafted.pptx", plan)
    dt += time.perf_counter() - t
    assert out[:2] == b"PK" and dt < 2.0, f"read, plan and fill took {dt:.1f} s"


def test_f1_pairs_are_not_read_past_the_body_cap():
    class B:
        def __init__(self, k):
            self.sid, self.x, self.y, self.cx, self.cy, self.size, self.text = k, 0, k * 10, 100, 5, 2000 - k, "t"

    assert read_pairs([B(k) for k in range(MAX_PAIR_BODIES + 1)], [], []) == ((), (), ())
    assert read_pairs([B(k) for k in range(2)], [], [])[0] != ()  # under the cap the search still runs
