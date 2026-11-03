# Rev 9 report to ai-brain-62

## Security audit F1 (from 28f22da)

Source final at c0b548e (fix 8a82f20, bundle rebuilt). Nothing pushed or published.

- Fix: read_pairs reads no pairs past MAX_PAIR_BODIES = 64 body boxes. clearing.goes builds `holds` only for a backing. A sample slide with more than MAX_SAMPLE_TEXT_BOXES = 500 text boxes is unusable (reason too_big).
- Flag: the audit asked for "more than 500 shapes". The cap counts text boxes instead, because sample-heavy (one sample of 1,503 shapes and 1 text box) is the rev 8 C30 and C12 stress fixture, which must stay usable and fill. The cost is in text boxes: the two caps alone take the 1,600-box read from 44.2 s to 0.34 s (decisions.tsv).
- Proof: tests/test_security_f1.py, three tests in 1.1 s. test_f1_crafted_1600_box_slide_reads_fast_and_is_unusable fails at 28f22da with "read took 44.2 s" (qa/security/f1-regression.txt).
- Counts: suite 509. G0c 4 of 4. G0b-r9 16 of 16. C5 105 of 105. C9 75 of 75. C10 8 of 8. Every G0c and G0b-r9 row equals round 3's: no pick changed.

## Codex round 2 fixes (fix round 3, from 2195cd2)

Source final at 6bcba11. Nothing pushed or published.

| item | commit | proving test |
|---|---|---|
| R2-1 a warned candidate ranks after any fitting one, for every title type | 2c183f1 | tests/test_c46_round1.py::test_r2_1_warned_normal_title_never_beats_a_fitting_display_title (sample-rank-floor: the display title fitting at 60 pt is chosen over the 60 pt title warned at its 42 pt floor) |
| R2-2 the title's orphan steps count in the ranking | 2c183f1 | ::test_r2_2_orphan_steps_count_in_the_ranking (sample-rank-orphan: 57 pt chosen over 54 pt) |
| R2-3 C23 allows pair geometry only inside a complete pair group | d0d544b | ::test_r2_3_c23_rejects_pair_geometry_without_a_complete_pair_group (r12: two pairs and an unpaired third B); demo c46-r23-no-group |
| E2-1 unclampable title anchor | not in this round | listed to Marco by ai-brain-62 |

Each of the three tests fails with its fix reverted: R2-1 and R2-2 by mutation in this run, R2-3 by the demo.

Counts: suite 506. G0c 4 of 4. G0b-r9 16 of 16 (0 slides for the eye, C23 differences 0). C5 105 of 105. C9 75 of 75. C10 8 of 8. Layout 213 of 213. Bundle rebuilt at 6bcba11.

Picks: none changed. The G0c rows (chosen samples and slides, both outlines and both faces) and all 16 G0b-r9 rows equal round 2's (f9753bd).

## QA round 2 (flag 2, from bc0291b)

Source final at f9753bd. Fable's ruling: flags 1 and 3 accepted; flag 2 fixed now.

- Change (2227701): Q9-3's orphan check runs the line-break estimate at the D12 Latin width (0.55 em) and at a condensed width (0.45 em), and the title steps down until neither run leaves one glyph alone (floor rule unchanged).
- Condensed width: Anton is embedded in qa/real-templates/canva-red-pink-pitch.pptx as ppt/fonts/font16.fntdata (EOT, flags 0, so readable). Its digits 0 and 2 to 8 advance 0.494 em (1 is 0.331, 9 is 0.504, space 0.234). The bare 0.49 does not reproduce the render: at 180 pt in the 1212 pt box the estimate still breaks before "800 ", so it sees no orphan. The deck sets Anton with tracking of -14.55 pt at its 297 pt size (-0.049 em), so its digit sets at 0.445 em, which rounds to 0.45 (also Fable's fallback). Recorded in decisions.tsv (flagged: the value includes the tracking).
- Proof: tests/test_c46_round1.py::test_r2_condensed_estimate_catches_the_orphan. On the r11 fixture, 0.55 em puts "800 萬" on line 2 (2 lines, 4 glyphs), 0.45 em puts 萬 alone (2 lines, 1 glyph), and the title is written at 48 pt. Demo c46-condensed-off fails mutated and passes restored; c46-orphan-kept re-run.
- Canva 預算 renders on one line at 140 pt, both faces, LibreOffice and Quick Look: qa/g0c/sheet-example-{mac,win}-{libreoffice,quicklook}.png slide 3 and qa/g0c/sheet-reference-{mac,win}-{libreoffice,quicklook}.png slide 4. Marco's deck sets "800 萬" together on line 2 (qa/g0b-r9/mac/marco-year-in-breakdowns/sheet.jpg slide 5).
- Counts: suite 503. G0c 4 of 4. G0b-r9 16 of 16, 0 slides for the eye, C23 differences 0. C5 105 of 105. C9 75 of 75. C10 8 of 8. Layout 213 of 213.

## QA fix round 1 and Codex round 1 (2026-11-03)

Source final at 0a61016 (bundle rebuilt there); evidence commits after it touch qa/, CHECKLIST.md and decisions.tsv only. Nothing pushed or published.

Counts: suite 502 passed (487 before). C9 75 of 75 (Mac and Windows user agents). C10/C28 8 of 8. C5 105 of 105. Layout route 213 of 213 equal. G0c script 4 of 4 (sheets qa/g0c/sheet-{example,reference}-{mac,win}-{libreoffice,quicklook}.png). G0b-r9 script 16 of 16, 0 slides for the eye (qa/g0b-r9/g0b-r9-report.json). C12 FAIL accepted, not re-run. Eye rows (G0c, G0b-r9, C46) PENDING with Fable.

| item | commit | proving test |
|---|---|---|
| Q9-1 unclampable box leaves the choice | ad8cc7a | tests/test_c46_round1.py::test_c46_q91_unclampable_box_leaves_the_subtitle_role, ::test_c46_q91_only_body_keeps_check, ::test_c46_q91_elegant_cover_has_no_check; G0b-r9 elegant PASS |
| Q9-2 warned two columns yield | ad8a97e | ::test_c46_q92_business_conference_budget_merges_on_s3 (S2 rule alone; fallback option not used); at the head ::test_c46_q92_business_conference_budget_unwarned_at_head (s10, flag 1) |
| Q9-3 no one-glyph last title line | 9eb8e28 | ::test_c46_q93_orphan_glyph_steps_the_title_down, ::test_c46_q93_title_at_its_floor_keeps_the_orphan; demo c46-orphan-kept (flag 2) |
| Q9-4 no empty frames | 7dd1bfd | ::test_c46_q94_cleared_caption_frame_goes_and_a_large_one_stays, ::test_c46_q94_canva_s6_has_no_empty_frame; demo c46-frame-kept |
| Codex F1 pair columns without built columns | 61ba187 | ::test_f1_pair_columns_without_built_columns |
| Codex F2 display steps past 7 in ranking | 5863ce3 | ::test_f2_display_title_steps_rank_past_seven |
| Codex F3 used bodies counted by text | 5b08ae3 | ::test_f3_pair_builds_count_only_boxes_with_text |
| Codex F4 C23 reads T5 pairs itself | eabd110 | ::test_f4_c23_rejects_geometry_from_a_non_pair; demo c46-f4-any-partner |
| Codex E1 clamp at the destination's floor | d13302d | ::test_e1_display_title_clamps_at_its_own_floor |
| Weak check C25 per paragraph | 7885ea5 | tests/test_c25_fit.py::test_c25_mixed_script_case_is_split_and_shrunk and the MIXED generic case |
| Weak check G0c donor and bold | fd8d305 | qa/g0c/run_g0c.py donor_problems in every G0c run; negative qa/g0c/donor-negative.txt (0 as written, 9 with bold stripped) |

Each Q9 test failed before its fix (b2b3c23) and each Codex E1 to F4 test fails with its fix reverted; the C25 mixed case is new coverage the per-run comparison could not run.

Flags:
1. Q9-2 against Codex F1: with F1, business-conference s7 and s10 offer pair columns with one slide and no warning; T5 ranks the two-column tier above the merge, so 預算 lands on s10, not round 3's merged s3 as C46 names. The S2 rule is proven with pair columns as they stood at 135093a. s10's columns spill below the yellow heading chips (qa/g0b-r9/mac/business-conference-slides/sheet-unmodified.jpg): Fable's eye.
2. Q9-3 is built on the estimate as written, but the Canva 預算 render still sets 萬 alone: the estimate counts Anton's digits at 0.55 em, so at 180 pt it puts "800 萬" on line 2 (4 glyphs) while the render keeps 800 on line 1. Marco's deck shows the same. Closing it needs a narrower Latin width for condensed display faces in the estimate, or an orphan test that also counts at a condensed width: Fable's call.
3. Q9-4's cause differs from the spec's wording: the backing test already ran on cleared boxes. The frames failed R5's fill read (a line and no fill element). Frame 15 also sat inside the joined title's union, so a cleared caption's backing drawn above a destination is no longer "behind" it; title fragments' blocks stay (C32).

Follow-ups:
- On the Canva deck, look_diff matches the cover copy (s1) to s7 by shared shape ids, giving 4 spurious differences on slide 1. The Canva C46 test checks the 問答 slide only.
- The unmodified LibreOffice sheets show Chinese as boxes, because PingFang HK and Microsoft JhengHei are not available to LibreOffice here. The typeface evidence is in G0c's Quick Look sheets.

## Build report (135093a)

Rev 9 is built on branch rev9-chinese, locally; nothing is pushed or published. Source final at 9e364c0; evidence and runners after it touch qa/ and tests/sample_look.py only.

## Counts

- Suite: 487 passed (433 at the start; qa/rev9/suite.txt).
- Failure demos: rev 9 adds 8 (c39-split-skipped, c40-unscaled-line, c41-ghost-anchor, c42-unclamped, c43-child-dropped, c43-child-in-b2, c44-no-title-growth, c45-refine-missing-layout); each fails mutated and passes restored (qa/failure-demos/).
- C9: 75 of 75, the session run on a Mac user agent (PingFang HK) and a Windows one (Microsoft JhengHei); privacy_proof PASS for both runs.
- C10/C28: 8 of 8 replays equal (cjk_face replayed).
- C5: 105 of 105 (the 4 G0c outputs and 4 rev 9 fixture outputs added).
- Layout route: 213 of 213 byte-equal to the 6a576a6 baseline.
- G0c script: 4 of 4. G0c eye: PENDING (Fable).
- G0b-r9 script: FAIL. The runner passes 14 of 16 runs: elegant-pitch-deck fails on both faces (a new check). business-conference 預算 is newly warned on both faces and listed for the eye; T2 is not its cause, so by the map rule it fails too unless Fable's eye finds otherwise. G0b-r9 eye: PENDING (Fable).
- C12: FAIL, 9 of 11 checks (run twice, the second with no other load): warm ready 5.1 s against a 5 s bar (round 3 4.9 s); longest task 3.84 s against a 3 s bar, on the 27 MB Canva deck that acd26e0 added to qa/real-templates (its fill is 2.31 s in CPython at the live commit 2ae997b and 2.50 s at the head; plan time rose from 0.01 s to 0.26 s with T5 and T6). Most of the overrun is the deck itself, present at the live commit too.

## Map

qa/rev9/MAP-STATUS.md holds the table with every rev 6 and rev 8 row, status, evidence path and commit.

## Flags (spec decisions that may be wrong; built as written)

1. T4 on elegant-pitch-deck: the cover's subtitle destination is the largest body box, a decorative "P" crossing the top-left edges; the left content margin is 328 pt, so the clamp inverts the box and falls back to check-this-slide. G0b-r9 counts the new check as a failure. A box that cannot be clamped could instead drop out of the destination choice (the next largest body takes the subtitle).
2. T5 with S1 on business-conference: pair columns make s2 (the Agenda slide) a two-column candidate with no continuation, so S1's class tier takes it before rev 8's merged content slide; s2's 285 by 72 pt title cannot grow over the panel behind it (the panel is 12.9% of the slide, so not a backing) and is warned at the 70% floor. Line spacing there is 120%, so T2 is not the cause. Treating a warned title as failing the readable pool, or preferring a candidate with no fit warning inside a tier, would keep round 3's pick.

## Unproven promises

- How PowerPoint (Windows and Mac), Keynote and Google Slides draw cjk_face: not proven here. C17 stays a deploy-gate row. Google Slides has no map row (note only).
- LibreOffice honours the embedded fonts; Quick Look ignores embedded fonts and alpha. Neither render stands for PowerPoint or Keynote.

## Leftovers (gitignored, not deleted)

qa/g0c/g0c-tmp-*/ and qa/g0c/renders/, qa/g0b-r9/*/*/renders-*/ and unmodified-*/ and the filled decks (about 2.3 GB together), the page-track worktree at .claude/worktrees/agent-af52d5b91e145d9aa (branch rev9-page), and fixtures/wui-tung-template.pptx still modified from 2026-11-01 (not committed).
