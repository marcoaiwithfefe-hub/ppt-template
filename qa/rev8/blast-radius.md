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

## QA round 3 (d1b3ca1..2dd5c96)

S1 changes only `plan_sample`'s pool choice on the sample route. Proven again: `qa/rev8/layout-head-qa3.json`, 213 of 213 baseline keys equal to 6a576a6 at 2dd5c96.

## QA round 3 S2 (ad434fe..cb09123)

S2 changes only the sample route's pool choice for two-column slides. Proven again: `qa/rev8/layout-head-qa3b.json`, 213 of 213 baseline keys equal to 6a576a6 at cb09123.

## Code review round 1 (057c266..b0ef3cf, branch fix-cr1)

**What it does.** F1 normalises every `mc:AlternateContent` to its fallback, in place on the reader's own `Presentation` (`read_samples`) and on each copy (`_copy_sample`). F2 makes custom-path corners that are guide names non-backings and turns any error while reading one sample slide into an unusable sample (`unreadable`, `Sample.error`). F3 mirrors flipped groups in `occ_box` and in the C23 comparator. F4 adds a merged variant of every content-tier sample for two-column slides. E1 counts the largest footer of each type in the deck, plus slack, and escaped text in the size budget; the fill's running guard now measures UTF-8 as saved. E2 marks remembered picks `switched` at route-switch time. Shared code the layout route runs: `open_template` still calls `read_samples` on every template, now with the normalisation, the per-slide `try` and the deck footer sizes.

**The one fact it is safe because of: the layout route is unchanged.** Step 4, ran real code. `qa/rev8/layout_baseline.py src qa/rev8/layout-head-cr1.json` at b0ef3cf: 213 of 213 baseline keys equal to 6a576a6, 0 differ, 0 missing (288 extra keys are later fixtures; the layout route fills every new one, sample-malformed included).

**Risks (real ones).**
- E1 refuses earlier. A template whose slides carry a large footer now has it counted on every copy, so a deck near the 40 MB cap is refused at planning instead of filled. Likelihood low (no G0, G0b or fixture template is near the cap; `test_c30_heavy_under_the_caps_fills` still fills 12 heavy copies). Check: C30 tests.
- F4 changes sample-route picks for two-column slides. Real templates: G0b reports equal to the S2 run (sheets byte-equal); Q5's edb-mpa2022 on the sample route goes from 9 to 7 slides (預算 merges on s5). Evidence: `qa/rev8/q5/cr1/`.
- Not changed, found while tracing: the Q1 clearing measures shapes with `to_slide`, which ignores rotation and flips by design, so a chip inside a flipped group is tested at its unflipped place (`src/deckfill/sample.py`, `shape_tree_leaves` qbox). F3 covered only the R3 grid. Unproven either way.
- Not changed: an unreadable sample slide's footer can still be borrowed by D4 step 1 on both routes (`fill._input_footers`). The layout route behaves as at 6a576a6 (baseline above); a malformed footer attribute would be copied, not raise, unless the target layout lacks that footer type (`_place_footer` reads its geometry). Unproven.

**Cleared.**
- `read_samples` mutating its `Presentation`: its only caller is `open_template`, whose `prs` is local and dropped after reading (`src/deckfill/template.py:384-402`).
- F1 speed: the first scan walked every element in Python; the C12 sample-xml stress fill rose from 5.46 s to 7.06 s. The tag-filtered scan (b0ef3cf) restores it: CPython fill 2.93 s at 057c266, 3.85 s before, 2.98 s after; C12 5.42 s.
- E2 and the download: a switched pick never reaches `fill`, because a switch disables the download until a plan succeeds, and a successful plan replaces the picks with the ones in use (`docs/app.js` `switchRoute`, `replan`).
- Privacy: C9 31 of 31 and `qa/e2e/privacy_proof.py` PASS at b0ef3cf.
