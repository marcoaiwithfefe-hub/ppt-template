# G0b result (rev 8, map rev 5)

Run on `8062bcf` (src unchanged since; the page work that follows does not touch `src/deckfill` fill logic) with `.venv/bin/python qa/g0b/run_g0b.py --before`. Outline: `fixtures/reference-outline.md`. Route: the one D11 picks (all eight pick `sample`). Renders: headless LibreOffice through `qa/g0b/lo_render.py` (render-only copy naming Arial Unicode MS as the East Asian face, private profile with the macOS Arial Unicode font; the delivered decks are untouched). Per-template evidence: `qa/g0b/<template>/report.json` (route, picks, flags per slide, warnings, script overlap check) and `qa/g0b/<template>/sheet.jpg` (every slide). Renders as PNG in `qa/g0b/<template>/renders/` (gitignored, rebuilt by the runner).

The gate's three tests, as run:
1. **Decoration**: every slide shows the template's look (background, photos, shapes). Seat's eye on the sheets.
2. **No text past a box unless the slide is warned or check-this-slide**: seat's eye on the sheets against each slide's flags in `report.json`.
3. **No two text boxes with text overlapping unless they overlap in the sample**: script. Every pair of text boxes holding text on an output slide whose slide-space boxes overlap, compared with the same pair on the sample it was copied from (`new_overlaps` in `report.json`). Text that runs past its own box on a warned slide is judged under test 2, not here.

| template | route | slides | flags (slide count) | new overlaps | verdict |
|---|---|---|---|---|---|
| corporate-sales-pitch-slides-2 | sample | 7 | shrunk 2, split 2 | 0 | clean |
| elegant-pitch-deck | sample | 7 | shrunk 4, split 2, warned 1 | 0 | clean (the title slide's subtitle wraps down its narrow sample box over the photo; that slide is warned) |
| 3d-modern-background-pitch-deck | sample | 7 | shrunk 4, split 2 | 0 | clean |
| business-conference-slides | sample | 9 | shrunk 8, split 5 | 0 | clean |
| simple-business-proposal-slides | sample | 7 | shrunk 1, split 2 | 0 | clean |
| viola-free-presentation-template | sample | 7 | shrunk 2, split 2 | 0 | clean (one sample's largest text is a small header, so 時間表 sits small at the top-left; it is the sample's own title box) |
| bullen-free-presentation-template | sample | 7 | shrunk 1, split 2 | 0 | clean |
| marco-year-in-breakdowns (Marco's) | sample | 13 | shrunk 11, split 10, warned 3 | 0 | clean, with two notes below |

**Verdict: 8 of 8 clean, Marco's template among them. Gate passed (bar: 7 of 8 with Marco's).**

Notes on Marco's template (for Fable's and Marco's eye):
- Title slide and the closing 問答 slide: the joined title runs across the four white word blocks of the sample's split title. Glyphs that land in the gaps sit on the dark photo and read poorly (`qa/g0b/marco-year-in-breakdowns/renders/slide-01.png`). The text stays inside its widened box, so test 2 is met, but it is the one place the look and the text fight.
- The three 預算 slides are warned. The only two-column sample (s3) has a 180 pt title box, and 預算 港幣 800 萬 does not fit one line even at the 70% floor, so at render the title grows over the right column's first line. That is text past a box on a warned slide (test 2 allows it), and the boxes themselves do not overlap (test 3).
- s6 copies show four blank white rectangles where the sample's big numbers were: the numbers are labels and are cleared, and their white backing shapes stay (D12: a decorated label shape stays as a shape).

Before and after on Marco's template: `qa/g0b/marco-before-after.jpg` (top: the layout route, every slide the same photo background, as Marco saw at `6a576a6`; bottom: the sample route).

## QA round 1 rerun (map rev 5 plus C32, C33)

Run on `55e6c76` plus the Q1 "behind a destination" fix committed with this file (src otherwise unchanged), with `.venv/bin/python qa/g0b/run_g0b.py`. The runner now also reports, per template, `blank_chips` (an output shape with a fill or line, no text, under 8% of the slide, that held sample text or holds 80% of a sample text box whose text is gone), `kept_under_text` (the same shapes when they sit behind an output text box, which Q1 keeps), and `title_bar` (the title slide's written title size against 4% of the slide height).

| template | slides (b38d280) | slides now | blank chips | kept under text | title slide title / bar | new overlaps | verdict |
|---|---|---|---|---|---|---|---|
| corporate-sales-pitch-slides-2 | 7 | 7 | 0 | 0 | 104 / 32.4 pt | 0 | clean |
| elegant-pitch-deck | 7 | 7 | 0 | 0 | 51 / 16.2 pt | 0 | clean |
| 3d-modern-background-pitch-deck | 7 | 7 | 0 | 0 | 48 / 16.2 pt | 0 | clean |
| business-conference-slides | 9 | 9 | 0 | 0 | 97 / 32.4 pt | 0 | clean |
| simple-business-proposal-slides | 7 | 7 | 0 | 0 | 80 / 16.2 pt | 0 | clean |
| viola-free-presentation-template | 7 | 9 | 0 | 0 | 28.5 / 16.2 pt | 0 | clean |
| bullen-free-presentation-template | 7 | 7 | 0 | 0 | 45.5 / 16.2 pt | 0 | clean |
| marco-year-in-breakdowns (Marco's) | 13 | 13 | 0 | 3 | 120 / 32.4 pt | 0 | clean by the QA round 1 definition, notes below |

**Verdict: 8 of 8 clean. Marco's template meets the three additions: the title slide's title meets the Q2 bar (120 pt on s7, bar 32.4 pt; it was 25.5 pt on s1), no blank chip (script 0; the s6 copies show no white rectangles on the sheet), and 13 slides beside rev 8's 13.**

Picks changed on two templates only (the other six pick what they picked at b38d280):
- Marco's: the title slide moves from s1 to s7 (Q2). 時間表 still splits into 4 slides on s6, 預算 into 3 warned slides on s3, 八項行動 into 3 on s5. The 時間表 body sits at 24 pt on an 810 pt slide (3% of the height, over the 2% bar). Every 2-slide candidate for 時間表 (s2, s3, s4) overflows its continuation title 時間表（續） at the floor, and a box over at the floor still ranks first (decisions row 93), ahead of Q4.
- Viola: 7 to 9 slides. The one-slide candidates for 時間表 and 預算 shrink their titles to 16 pt, under the 16.2 pt bar, so the readable pool holds only samples that split once each (s4, s27).

Eye notes on Marco's template (renders in `qa/g0b/marco-year-in-breakdowns/renders/`):
- 問答 on s1: the three white word blocks under the joined title stay (they lie under the destination's widened box, so Q1 keeps them); 問答 is centred across them as at b38d280. Without them, the first QA round 1 run drew 問答 black on the photo (that run is not kept).
- s1's olive leaf (shape 74, 4.1% of the slide) is gone on 問答: it holds over 80% of the last year-digit label's box, so Q1 reads it as that label's backing. The four orange circles under the year digits go the same way.
- 預算 on s3 stays warned on all three slides: the title runs onto the body's first line at the floor.

Before and after on Marco's template: `qa/g0b/marco-before-after-qa1.jpg` (top: b38d280; bottom: this run).
