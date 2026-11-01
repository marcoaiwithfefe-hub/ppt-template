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
