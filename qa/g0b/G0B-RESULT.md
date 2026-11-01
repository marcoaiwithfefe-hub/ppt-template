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
