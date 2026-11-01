# Q5: rev 7's real templates on both routes (QA round 1)

Run on `104dc38` with `.venv/bin/python qa/rev8/q5/run_q5.py`: each template filled with `fixtures/reference-outline.md` on the layout route and on the sample route, rendered with the G0b renderer. D11 is unchanged; these sheets are for Fable's call on its default. Side-by-side images (left layout, right sample): `edb-mpa2022-both.jpg`, `elderly-gov-diy-both.jpg`, `hkust-template14-both.jpg`. Per-route reports and sheets in `<template>-<route>/`; summary in `q5-runs.json`.

| template | D11 default | layout route | sample route | sample-route flags | what the sheets show |
|---|---|---|---|---|---|
| edb-mpa2022 | sample | 7 slides | 18 slides (s2, s5, s4, s5, s3, s2) | 15 slides split, 2 warned | Layout: plain yellow stripe layouts, all text readable. Sample: the cartoon look on every slide, but 時間表 takes 4 slides and 八項行動 takes 8, one bullet each, under a repeated 八項行動（續）. s5 holds 八項行動 in 2 slides, but 預算 used it on the slide before, so variety removes it from the pool before the ranking (QA3 order); s3 is left, one bullet a slide. |
| elderly-gov-diy | sample | 7 slides | 7 slides (s1, s14, s9, s8, s16, s1) | shrunk on 4, 八項行動 split once | Layout: a near-blank white layout with one music-note picture. Sample: the template's globe cover, drawings and icons carry over; text readable; one icon row on 時間表 stays from the sample. |
| hkust-template14 | sample | 9 slides | 11 slides (s2, s9 x4, s2) | warned on all 11 | Layout: the HKUST photo layouts, titles and bullets readable. Sample: only 2 usable samples (7 of 9 have no title box); their title boxes are narrow vertical strips, so every title is set one glyph per line down the strip and warned. |

Seat's reading: the sample route is better on elderly-gov-diy and worse on edb-mpa2022 and hkust-template14. Fable's call on D11.

## QA round 2 (R1 to R7), sheets in `qa2/` beside round 1's

Run on `7d9dbde` with `.venv/bin/python qa/rev8/q5/run_q5.py qa2`.

| template | D11 default now | layout route | sample route, round 1 | sample route, round 2 |
|---|---|---|---|---|
| edb-mpa2022 | sample | 7 slides | 18 | 9 (s2, s5 for four outline slides, s2): 時間表 1, 預算 3, 八項行動 2 |
| elderly-gov-diy | sample | 7 | 7 | 7 (s9, s14, s10, s9, s8, s2) |
| hkust-template14 | layout (R4: 2 usable samples) | 9 | 11 | 11, every slide still warned (the narrow vertical title strips) |

Sheets: `qa2/edb-mpa2022-both.jpg`, `qa2/elderly-gov-diy-both.jpg`, `qa2/hkust-template14-both.jpg`.
