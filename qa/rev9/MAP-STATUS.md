# Rev 9 map status (map rev 6 plus the rev 8 rows)

Source under test: rev 9 with QA rounds 1 and 2, Codex rounds 1 and 2 and security audit F1, source final at c0b548e; G0c, G0b-r9, C5, C9 and C10 re-run there (rows equal to round 3 at 6bcba11); other rows at the commit they name.
Suite: 509 passed (qa/rev9/suite-sec1.txt; 487 at 135093a). Statuses: PASS, FAIL, NOT RUN, PENDING. Eye rows are Fable's.

## Map rev 6 (rev 9)

| id | status | evidence | commit |
|---|---|---|---|
| C39 Chinese face | PASS (script) | tests/test_c39_c40_type.py (both faces; Extension B and halfwidth katakana; step 3 line only when T1 fired; budget counts extra runs, one-run budget under-counts a near-cap line); qa/e2e/c9-report.json C39 7 of 7 per user agent (Mac PingFang HK, Windows Microsoft JhengHei, a:ea face in the download); demo qa/failure-demos/c39-split-skipped-*.txt | 9e364c0, C9 at 2a0ee5d |
| C40 Chinese line height | PASS | tests/test_c39_c40_type.py C40 cases; tests/test_c25_fit.py t2_line on every C25 box; demo c40-unscaled-line | 9e364c0 |
| C41 watermarks | PASS | tests/test_c41_c42_marks.py; golden tests/goldens/sample/ghost.golden; sample-ghostd11 keeps layout; demo c41-ghost-anchor | 9e364c0 |
| C42 edge clamp | PASS | tests/test_c41_c42_marks.py (title, body, group, fallback with check, C23 rejects an undeclared box); tests/test_c43_pairs.py::test_c42_pair_destination_clamped; demo c42-unclamped | 9e364c0 |
| C43 pairs | PASS | tests/test_c43_pairs.py; golden tests/goldens/sample/pairs.golden (hand-written from T5); demos c43-child-dropped, c43-child-in-b2 | 9e364c0 |
| C44 title growth | PASS | tests/test_c44_titlegrow.py; C25 floor per box (tests/test_c25_fit.py floor_for); demo c44-no-title-growth | 9e364c0 |
| C45 first-draft line | PASS | qa/e2e/c9-report.json C45 5 of 5 per user agent (layout and sample routes, hidden before download, byte-equal to copy.js); demo qa/failure-demos/c45-refine-missing-layout-*.txt (69 passed, 6 failed mutated; 75 of 75 restored) | 7305482, C9 at 2a0ee5d |
| G0c script | PASS 4 of 4 | qa/g0c/g0c-report.json (now also C39's donor and display-bold rule on every written box, Codex weak check; negative qa/g0c/donor-negative.txt: 0 problems as written, 9 with bold stripped); C5 qa/c5/c5-report.json (4 G0c outputs, 0 errors); logs qa/rev9/g0c-qa1.log to qa/rev9/g0c-qa3.log | 6bcba11 |
| G0c eye | PENDING (Fable) | qa/g0c/sheet-{example,reference}-{mac,win}-{libreoffice,quicklook}.png; per-slide renders under qa/g0c/renders/ (gitignored). Neither LibreOffice nor Quick Look proves how PowerPoint or Keynote draw the deck. 預算 港幣 800 萬 sets one line on all 8 sheets at round 2 (no lone 萬); round 3 rows identical to round 2 | 6bcba11 |
| G0b-r9 script | PASS 16 of 16 | qa/g0b-r9/g0b-r9-report.json, logs qa/rev9/g0b-r9-qa1.log to qa/rev9/g0b-r9-qa3.log: slide counts equal or lower on all 8 (marco 9 to 8), no new continuation, no new check, warned or small_text (0 slides for the eye), C23 differences 0; round 3 rows identical to round 2 | 6bcba11 |
| G0b-r9 eye | PENDING (Fable) | qa/g0b-r9/{mac,win}/<template>/sheet-unmodified.jpg (typeface evidence; LibreOffice has no PingFang HK or Microsoft JhengHei here, so Chinese shows as boxes), sheet.jpg (geometry only, East Asian faces rewritten); round 3 sheets at 2ae997b:qa/g0b/<template>/sheet.jpg; picks changed listed per row (business-conference 預算 now s10 pair columns; marco 預算 and 八項行動 on s5 pair columns, its white cards removed with the cleared bodies; its 預算 now sets 800 萬 together on line 2) | 6bcba11 |
| C46 round 1 fixes (with Codex round 2 R2-1, R2-2: tests/test_c46_round1.py::test_r2_1_*, ::test_r2_2_*, 2c183f1) | PASS (script); eye PENDING | tests/test_c46_round1.py: Q9-1 subtitle to the next body box with no check, the only-body fallback keeps check, elegant cover no check; Q9-2 merged s3 with pair columns as at 135093a, and at the head 預算 one slide with no warning (s10, flag 1); Q9-3 54 pt step-down, floor keeps the orphan; Q9-4 fixture frame goes and the 9.1% frame stays, Canva s6 frames 6, 11, 15 gone. Demos qa/failure-demos/c46-orphan-kept-*.txt, c46-frame-kept-*.txt (fail mutated, pass restored). G0b-r9 16 of 16, G0c 4 of 4 at the fix head. Round 2 (flag 2): the orphan check also runs at 0.45 em (Anton's digit as the Canva deck sets it); tests/test_c46_round1.py::test_r2_condensed_estimate_catches_the_orphan (0.55 em sees 800 萬 on line 2, 0.45 em sees 萬 alone, written 48 pt), demo c46-condensed-off; Canva 預算 one line at 140 pt on both faces, LibreOffice and Quick Look | 7dd1bfd, 2227701, f9753bd |


| Security F1 slow read | PASS | tests/test_security_f1.py (3 tests); qa/security/f1-regression.txt (fails at 28f22da: read 44.2 s) | 8a82f20 |

## Rev 8 rows (map rev 5 and QA rounds 1 to 3)

| id | status | evidence | commit |
|---|---|---|---|
| G0b | see G0b-r9 (same checks re-run) | qa/g0b-r9/g0b-r9-report.json | 6bcba11 |
| C22 route choice | PASS | tests/test_c22_route.py; C9 C22 3 of 3 per user agent | 9e364c0 |
| C23 look carried | PASS | tests/test_c23_look.py; comparator reads T5 pairs and complete slot groups itself (Codex F4 and R2-3: tests/test_c46_round1.py::test_f4_c23_rejects_geometry_from_a_non_pair, ::test_r2_3_c23_rejects_pair_geometry_without_a_complete_pair_group; demos c46-f4-any-partner, c46-r23-no-group) | d0d544b |
| C24 no sample text | PASS | tests/test_c24_c27_sample_text.py (18 goldens) | 9e364c0 |
| C25 fit | PASS | tests/test_c25_fit.py (T2 lines, T6 floors; sizes per paragraph across T1's split runs with a mixed-script shrunk case, Codex weak check) | 7885ea5 |
| C26 copies open clean | PASS | tests/test_c26_c29_c30_sample.py; qa/c5/c5-report.json 105 of 105 | 0faa60c |
| C27 no text lost | PASS | tests/test_c24_c27_sample_text.py | 9e364c0 |
| C28 browser equals tests | PASS | qa/e2e/c10_compare.py 8 of 8 (sample-design and sample-latin-font replayed with the page's cjk_face) | 6bcba11 |
| C29 sample footers | PASS | tests/test_c26_c29_c30_sample.py | 9e364c0 |
| C30 limits | PASS | tests/test_c26_c29_c30_sample.py; C39 budget case | 9e364c0 |
| C31 picker | PASS | qa/e2e/c9-report.json C31 2 of 2 per user agent | 2a0ee5d |
| C32 to C37 | PASS | tests/test_c32_c33_readable.py, tests/test_c34_c37_round2.py | 9e364c0 |
| C38 covers | PASS | tests/test_c38_covers.py | 9e364c0 |
| C9 privacy | PASS | qa/e2e/c9-report.json 75 of 75 (logs qa/rev9/c9-qa1.log to qa/rev9/c9-qa3.log) | 6bcba11 |
| C5 validator | PASS | qa/c5/c5-report.json 105 of 105 (logs qa/rev9/c5-qa1.log to qa/rev9/c5-qa3.log) | 6bcba11 |
| C12 load | FAIL (2 of 11 checks, run twice, the second with no other load) | qa/e2e/c12-report.json: warm ready 5.1 s (bar 5 s; round 3 4.9 s); longest task 3.84 s on canva-red-pink-pitch.pptx (bar 3 s), a 27 MB template that entered qa/real-templates with acd26e0, whose fill takes 2.31 s in CPython at 2ae997b and 2.50 s at the head (plan 0.01 s to 0.26 s with T5 and T6). The other 9 pass, the sample-route stress cases included | a81dfaf |
| C17 Windows PowerPoint | PENDING (deploy gate) | not runnable here | |
| Layout route unchanged | PASS 213 of 213 | qa/rev9/layout-head-qa1.json to qa/rev9/layout-head-qa3.json against qa/rev8/layout-baseline-6a576a6.json | 6bcba11 |

## Limits named

- How PowerPoint on Windows, Keynote and PowerPoint on a Mac draw cjk_face is not proven by any check here (C17 stays a deploy-gate row).
- Google Slides (no map row): not tested; it substitutes faces it lacks, and whether it maps Microsoft JhengHei or PingFang HK to a Chinese face is unknown.
- Quick Look ignores embedded fonts and alpha (ghosts draw opaque); LibreOffice honours embedded fonts; neither stands for PowerPoint.
