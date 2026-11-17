# Build checklist

- [x] deckfill module: read_template, parse_outline, plan_deck, fill
- [x] fixture templates by script (fixtures/make_fixtures.py), rels-order added at G0
- [x] CPython tests: C1, C2, C3, C4, C5 (integrity part), C6, C7, C8, C11 (169 pass at 6d430ea)
- [x] C5 validator: Open XML SDK console tool in tools/validate; SDK installed by Marco 2026-10-30; 37 of 37 outputs pass, HKUST 14 on a provisional allowlist entry for its template's own error, settled by C17 (qa/c5/c5-report.json); failure demo in qa/failure-demos/c5-validator-*.txt
- [x] G0: 5 real templates, renders, verdict (4 of 5 clean on every part, validator included; HKUST 14 outside the five has 1 template-owned validator error; qa/g0/G0-RESULT.md)
- [x] Page: docs/, Cantonese copy file, Mentron look, CSP and lockdown (copy waits on Marco's Rule 25 proof)
- [x] Pyodide self-hosted and pinned (314.0.7)
- [x] PROMPT.md, skill/ppt-outline/SKILL.md, README.md, LICENSE (README and page copy wait on Marco's Rule 25 proof)
- [x] End-to-end (Playwright): C8 page part, C9, C10, C12, C13 (all pass at rev 5; warm load 4.9 s near the bar; worst-case heap 1,384 MB with MAX_TOTAL 130 MB)
- [x] C14 copy floors, C15 Gemini outlines (C14 script part pass, Codex half pending; C15 3 of 3 pass)
- [x] D10 demo deck and renders (qa/demo/; C1, C3, C5 integrity pass; validator 0 errors)
- [x] Failure demos for C1, C2, C4, C5, C9 in qa/failure-demos/ (qa/failure-demos/run_demos.py; C3 rels-order and C4 slide-number extra; C5 validator demo in c5-validator-*.txt)
- [x] Slop scan triage (qa/slop-triage.md: 2 hits, both kept)
- [x] blast-radius: privacy proof from a saved request log (qa/blast-radius.md, qa/e2e/privacy_proof.py PASS on fc505ff)
- [x] Walkthrough rendered to qa/walkthrough/ (not published)
- [x] Rev 5: caps 100 MB file, uncompressed 150 MB lowered to 130 MB for the heap bar; copy, tests, worst case, C12, G0 sixth run, notes
- [x] Report to ai-brain-52
- [x] Codex round 1: F1 to F14 fixed with failing-first tests (qa/codex1/fixes/); final rerun on e85ebd9, evidence 72fb67e, walkthrough fd78e9f
- [x] Layout-override fix (after round 1, MAJOR): picks follow their slide by title, kind and nth; gone or misfit picks drop with a note; tests fail before at b5db511, pass at 247fa54 (qa/override-fix/); C19 list in qa/c19/PROOF-LIST.md
- [x] Codex round 2: F15, F3 partial, F10 partial fixed with failing-first runs (qa/codex2/fixes/); C14 format evidence (qa/c14/google-format.md); G0 Fable-view line; rerun on c038a9b
- [x] Codex round 3: F16 (same-titled picks) fixed with failing-first runs (qa/codex3/fixes/); layout_gone reworded (C19 list); rerun on edaae49

## Rev 8 (sample-slide route, map rev 5) and QA round 1

- [x] sample.py reading: D11 availability and default, D12 title region, labels, slots, donor runs, effective sizes
- [x] sample_plan.py: D12 planning, fit with spAutoFit modelled, limits (too_big before allocating)
- [x] sample_fill.py: copy step, donor text, title widening, footers rebuilt once, clearing
- [x] 22 rev 8 fixtures by fixtures/make_sample_fixtures.py; C22 to C27, C29, C30 tests with independent oracles
- [x] Failure demos C24, C26, C27 reject their mutations; rev 7 C1 to C5 demos still reject theirs
- [x] G0b: 8 of 8 clean (qa/g0b/G0B-RESULT.md)
- [x] Page: route line and switch, 範本頁 picker, fit states incl. 字細咗; deckfill.zip rebuilt from src
- [x] End-to-end: C9 session incl. C22 page part and C31, C10/C28 full override replay, C12 with sample stress cases
- [x] QA round 1: Q1 chips and backings, Q2 and Q3 readability bars, Q4 fewest continuation slides, precedence, small_text (字細 in docs/copy.js); C23 comparator computes the Q1 removals itself; C32 and C33 tests fail on b38d280 and pass at head (qa/qa1/)
- [x] QA round 1: shapes under a kept destination's box stay (Marco's 問答 title on s1)
- [x] Q5: edb-mpa2022, elderly-gov-diy, hkust-template14 on both routes (qa/rev8/q5/Q5-RESULT.md); D11 unchanged
- [x] G0b rerun with the QA round 1 clean definition; qa/g0b/marco-before-after-qa1.jpg
- [x] C5 validator on every output incl. the sample-route fixtures, G0b decks, C28 and Q5 sample outputs
- [x] Fill time, click to download, Bullen and Marco's template, three runs cold and warm (qa/e2e/fill-time.json)
- [x] C19 proof list gains the rev 8 strings and 字細
- [x] Blast radius: layout route 213 of 213 keys equal to 6a576a6 at the final code commit (qa/rev8/)
- [x] Slop scan once (qa/slop-triage.md, rev 8 section)
- [x] Walkthrough rendered to qa/walkthrough/rev8/ (not published)
- [x] Report to ai-brain-24 [75678f] (QA round 1)

## Rev 8 QA round 2

- [x] R4 route default (design test and 3 usable content samples), R7 slots must fit, R2 continuation titles, R1 order with R6 pool, R3 grown body with its own backing, R5 backings by geometry (eedcf10 groundwork, 7d9dbde)
- [x] C23 comparator: R5 backings, R3 growth with an independent grid, exclusive C14N; C34 to C37; C22 sample-thin defaults to layout; round 2 tests fail on eedcf10 (qa/qa2/)
- [x] Stale c24 demo anchors retargeted; all 15 failure demos reject their mutations
- [x] 版面調整 in docs/copy.js and the C19 list; page font subset rebuilt; deckfill.zip rebuilt
- [x] G0b rerun with the round 2 checks, fresh render folders, C23 on every real deck; qa/g0b/marco-before-after-qa2.jpg
- [x] Q5 rerun, sheets in qa/rev8/q5/qa2/ beside round 1's
- [x] C5 on the round 2 fixtures and Q5 sample outputs; the other grown cases validated (qa/qa2/c5-grow-cases.txt)
- [x] Slop scan once (docs changed)
- [x] End-to-end, fill time, layout baseline 213 of 213, walkthrough re-rendered
- [x] Report to ai-brain-24 [75678f] (QA round 2)

## Rev 8 QA round 3

- [x] S1 class first inside the readable pool (2dd5c96); C38 (tests/test_c38_covers.py) fails on d1b3ca1 and passes at head (qa/qa3/)
- [x] design.golden re-derived by hand; the other golden cases keep their picks (qa/qa3/golden-picks-d1b3ca1-vs-head.txt)
- [x] G0b rerun with title slides and two-column slides reported; qa/g0b/title-slides-qa3.jpg; qa/g0b/marco-before-after-qa3.jpg
- [x] Done gates at the final head: suite, failure demos, C5, C9, C10/C28, C12, fill time, layout baseline 213 of 213, slop scan once, walkthrough re-rendered
- [x] Report to ai-brain-24 [75678f] (QA round 3)
- [x] S2 two columns yield when they add slides (cb09123); C38 gains both cases, the yield case fails on ad434fe (qa/qa3/before-ad434fe-s2.txt)
- [x] G0b with S2: Marco's 預算 3 -> 2, business-conference's 3 -> 1; qa/g0b/marco-before-after-qa3b.jpg
- [x] Done gates at the S2 head; walkthrough over the whole range 6a576a6..head for the Codex code review loop
- [x] Report to ai-brain-24 [75678f] (QA round 3 S2)

## Code review round 1 (fix-cr1 from 057c266)

- [x] F2 guide-name paths are not backings; a sample that fails to read is unreadable, never the template (1a70b24; demos f2-guide-path, f2-sample-isolation)
- [x] F1 copies and the reader hold only fallback branches; C24 oracle lists choice text (d6b4778, b0ef3cf; demo f1-choice-kept)
- [x] F3 flipped groups in occ_box and the C23 comparator (ec50cf0)
- [x] F4 S2 compares a two-column sample's own merged variant (2914b63)
- [x] F6 C25 resolves output sizes and paragraph properties independently (8530535; demos f6-*)
- [x] E1 size budget counts borrowed footers and escaped text (42c6621)
- [x] E2 route switch forgets picks at once (1b686bd; demo e2-picks-kept-on-switch)
- [x] F5 C5 runner validates exactly its manifest; 88 of 88 (1ed65b0)
- [x] Done gates: suite, demos, G0b, Q5 (qa/rev8/q5/cr1), C9, C10/C28, C12, C5, layout baseline 213 of 213, blast radius
- [x] F7 walkthrough re-rendered over 6a576a6..head
- [x] Report to ai-brain-24 [75678f] (code review round 1)

## Code review round 2 (fix-cr2 from 22f64da)

- [x] N1 Q1 clearing on drawn bounds in production and in the C23 comparator; flipped and rotated chip cases fail at 22f64da (aa02dc1; demo n1-unrotated-bounds)
- [x] Edge 1 a footer whose idx does not parse is skipped on both routes; fixture sample-badidx (71c7cea; demo edge1-bad-idx-borrowed)
- [x] Edge 2 footer sizes read from raw XML before footer_boxes; fixture sample-footbad (71c7cea; demo edge2-footer-size-after-box)
- [x] Done gates: suite, demos 24 of 24 plus C5 validator, C5 92 of 92, C9, C10/C28, C12, G0b, Q5 (qa/rev8/q5/cr2), layout baseline 213 of 213, blast radius
- [x] Walkthrough re-rendered over 6a576a6..head
- [x] Report to ai-brain-24 [75678f] (code review round 2)

## Code review round 3 (fix-cr3 from 3df373e)

- [x] footer idx checked with int(); "²" case fails at 3df373e (9fcfc40; demo cr3-idx-isdigit)
- [x] footer with an unreadable a:off or a:ext skipped on both routes; skipped footers not budgeted; sample-footbad in C5 (9fcfc40; demo cr3-footer-box)
- [x] Gates: suite, 26 mutation demos plus C5 validator, C5 97 of 97, layout baseline 213 of 213, G0b and Q5 unchanged, C9, C10/C28
- [x] Walkthrough re-rendered; report to ai-brain-24 [75678f] (code review round 3)

## Rev 9 (branch rev9-chinese from acd26e0): Chinese type and showcase decks

- [x] Fixtures: sample-latin-font, sample-ghost, sample-ghostd11, sample-pairs, sample-titlegrow (fixtures/make_rev9_fixtures.py)
- [x] C39 and C40 checks with negative demos, failing before T1 and T2
- [x] T1 Chinese face: run split, cjk_face input on plan_deck and the bridge, size budget counts the extra runs, step 3 flag
- [x] T2 line height: spcPts scaled to the written size, Chinese floors, estimate uses the written values (C25 extended)
- [x] C41 to C44 checks with negative demos, each failing before its stage
- [x] T3 watermarks and echoes
- [x] T4 edge clamp
- [x] T5 heading and body pairs
- [x] T6 title growth and display floor
- [x] T7 first-draft line (refineNote) and C45 (demo c45-refine-missing-layout)
- [x] Page: cjk_face from navigator.userAgent, step 3 face line, docs bundle rebuilt
- [x] C9 session on a Mac and a Windows user agent (75 of 75); C10 and C28 replays with cjk_face (8 of 8)
- [x] C5 validator manifest gains the G0c outputs and the rev 9 fixture outputs (105 of 105)
- [x] G0c script 4 of 4: Canva deck, both outlines, both faces, LibreOffice and Quick Look renders in qa/g0c/ (eye pending, Fable)
- [x] G0b-r9 against round 3's report at 2ae997b (FAIL: elegant cover check, business-conference 預算 warned; eye pending)
- [x] Map rev 6 plus rev 8 rows reported with evidence and commit (qa/rev9/MAP-STATUS.md)
- [x] Walkthrough over acd26e0..HEAD in qa/walkthrough/rev9/
- [x] Report to ai-brain-62 [feb9f3] (head ad6169e)

## Rev 9 QA round 1 (from b11f819) with Codex round 1

- [x] C46 fixtures (sample-round1 r1 to r5) and tests, failing first (b2b3c23)
- [x] Q9-1 unclampable box leaves the choice (ad8cc7a)
- [x] Q9-2 warned two columns yield to the merge (ad8a97e)
- [x] Q9-3 no one-glyph last title line (9eb8e28)
- [x] Q9-4 no empty frames (7dd1bfd), demos c46-orphan-kept and c46-frame-kept
- [x] Codex E1 clamp floor (d13302d), F2 rank steps (5863ce3), F3 used bodies (5b08ae3), F1 pair columns without built columns (61ba187), F4 C23 pair eligibility and demo (eabd110)
- [x] Weak checks: C25 per paragraph (7885ea5), G0c donor and bold rule (fd8d305); qa/codex-rev9-1 committed
- [x] Bundle rebuilt (0a61016); suite 502; C9 75 of 75; C10 8 of 8; C5 105 of 105; layout 213 of 213
- [x] G0c 4 of 4, G0b-r9 16 of 16 at the fix head
- [x] Walkthrough over acd26e0..HEAD re-rendered in qa/walkthrough/rev9/
- [x] REPORT.md and MAP-STATUS.md updated; decisions.tsv rows dated 2026-11-03T20
- [x] Report to ai-brain-62 [feb9f3]

## Rev 9 QA round 2 (flag 2, from bc0291b)

- [x] Anton's digit advance read from the embedded font (0.494 em; 0.45 em with the deck's tracking), decisions.tsv
- [x] Orphan check at 0.55 and 0.45 em (2227701), test_r2_condensed_estimate_catches_the_orphan, demo c46-condensed-off
- [x] Bundle rebuilt (f9753bd); suite 503; G0c 4 of 4 (預算 one line on every sheet); G0b-r9 16 of 16; C5, C9, C10, layout
- [x] Walkthrough re-rendered; REPORT.md and MAP-STATUS.md updated
- [x] Report to ai-brain-62 [feb9f3]

## Codex round 2 fixes (fix round 3, from 2195cd2)

- [x] R2-1 warned ranks after any fit (2c183f1), test_r2_1_*, fixture sample-rank-floor
- [x] R2-2 orphan steps in the ranking (2c183f1), test_r2_2_*, fixture sample-rank-orphan
- [x] R2-3 C23 complete pair groups (d0d544b), test_r2_3_*, fixture r12, demo c46-r23-no-group
- [x] Bundle rebuilt (6bcba11); suite 506; G0c 4 of 4; G0b-r9 16 of 16; C5, C9, C10, layout; no pick changed
- [x] Walkthrough re-rendered; REPORT.md and MAP-STATUS.md updated; qa/codex-rev9-2 committed
- [x] Report to ai-brain-62 [feb9f3]

## Security audit F1 and the deploy branch (from 28f22da)

- [x] F1 caps (8a82f20), tests/test_security_f1.py, qa/security/f1-regression.txt; bundle rebuilt (c0b548e)
- [x] Suite 509; G0c 4 of 4; G0b-r9 16 of 16; C5, C9, C10; no pick changed
- [x] F2 deploy branch rev9-deploy from main, one commit, private paths excluded, not pushed
- [x] Report to ai-brain-62 [feb9f3]
