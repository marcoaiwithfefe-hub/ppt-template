# Blast radius, rev 8 with QA round 1 (6a576a6..6d9a809)

**What it does.** Adds the sample-slide route (D11, D12) and QA round 1's readability rules, chips and backings. Shared code that the layout route also runs: `plan.height` gains a wrapping-off branch (taken only when `Fit.nowrap` is set, which only the sample route sets), `fill.footers_for` is split into `footer_for_type` (same body, one type at a time), `plan_deck` and `fill` branch on `route`, `open_template` reads every sample slide and works out the routes and the default, and `web.Session` sends the route.

**The one fact it is safe because of: the layout route is unchanged.** Proven by running code (step 4). `qa/rev8/layout_baseline.py` fills every rev 7 fixture and G0 real template from every rev 7 outline with `route="layout"` and digests every output part (canonical XML, SHA-256 for binaries).

- 6a576a6 baseline: `qa/rev8/layout-baseline-6a576a6.json`, 213 keys.
- Head 6d9a809: `qa/rev8/layout-head-6d9a809.json`. 213 of 213 baseline keys equal, 0 differ (the 204 extra keys are templates made after 6a576a6).
- The check bites: the same run on a scratch copy of head src with `fill.py` dropping the last body paragraph differs on 198 of 213 keys.

**Risks (real ones).**
- Default route moved for some rev 7 templates, by design: edb-mpa2022, elderly-gov-diy and hkust-template14 now open on the sample route (decisions row 103). Q5 shows that is worse on two of them (`qa/rev8/q5/Q5-RESULT.md`); D11 waits on Fable.
- A caller that calls `plan_deck` without `route` now gets the template's default route. Every in-repo caller passes it or wants the default: the G0 runner and the layout baseline pin `layout`, the page and `web.Session` pass the page's route, the C5 runner and G0b pass `sample` or the default on purpose.
- `read_template` now reads sample slides on every template, so a sample-slide oddity runs on the layout route's read too. All 8 G0b, 6 G0 and 37 fixture templates read; a probe that set a malformed run size on every sample run of `footer-active.pptx` still read. Not traced further: a different malformed attribute could still raise outside `DeckfillError` (unproven either way).

**Cleared.** `plan.height`'s new branch: `Fit.nowrap` defaults to False and only `sample.SBox.fit_at` sets it (`src/deckfill/template.py`, `src/deckfill/sample.py`). `footer_for_type`: the layout route's C4 tests and the 213-key baseline cover it. Privacy: C9 30 of 30 and `qa/e2e/privacy_proof.py` PASS at 6d9a809 (zero page requests after ready).

## QA round 2 (eedcf10..8cccd6b)

The shared code the layout route runs did not change in round 2: R1 to R7 live in `sample_plan.py`, `sample.py` and `sample_fill.py`, which the layout route never calls; `open_template` changed only through `sample_default` (R4), which moves the default route of templates with fewer than 3 usable samples (hkust-template14, sample-thin, sample-shapes, sample-xml) to the layout route without changing what that route builds. Proven again by running code: `qa/rev8/layout-head-qa2.json`, 213 of 213 baseline keys equal to 6a576a6 at 8cccd6b. Risk found and fixed in the gates: R4 moved the C12 sample-route stress templates onto the layout route, so the stress check now switches routes and requires the sample route.
