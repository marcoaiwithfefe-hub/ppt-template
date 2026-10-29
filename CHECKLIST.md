# Build checklist

- [x] deckfill module: read_template, parse_outline, plan_deck, fill
- [x] fixture templates by script (fixtures/make_fixtures.py), rels-order added at G0
- [x] CPython tests: C1, C2, C3, C4, C5 (integrity part), C6, C7, C8, C11 (169 pass at 6d430ea)
- [ ] C5 validator: Open XML SDK console tool in tools/validate (code written; BLOCKED: dotnet SDK install refused by the permission classifier, needs Marco)
- [ ] G0: 5 real templates, renders, verdict (4 of 5 clean, validator part NOT RUN; qa/g0/G0-RESULT.md)
- [x] Page: docs/, Cantonese copy file, Mentron look, CSP and lockdown (copy waits on Marco's Rule 25 proof)
- [x] Pyodide self-hosted and pinned (314.0.7)
- [x] PROMPT.md, skill/ppt-outline/SKILL.md, README.md, LICENSE (README and page copy wait on Marco's Rule 25 proof)
- [x] End-to-end (Playwright): C8 page part, C9, C10, C12, C13 (all pass; warm load 5.0 s at the bar)
- [x] C14 copy floors, C15 Gemini outlines (C14 script part pass, Codex half pending; C15 3 of 3 pass)
- [x] D10 demo deck and renders (qa/demo/; C1, C3, C5 integrity pass; validator NOT RUN)
- [x] Failure demos for C1, C2, C4, C5, C9 in qa/failure-demos/ (qa/failure-demos/run_demos.py; C3 rels-order and C4 slide-number extra; C5 validator part NOT RUN)
- [x] Slop scan triage (qa/slop-triage.md: 2 hits, both kept)
- [x] blast-radius: privacy proof from a saved request log (qa/blast-radius.md, qa/e2e/privacy_proof.py PASS on fc505ff)
- [x] Walkthrough rendered to qa/walkthrough/ (not published)
- [ ] Report to ai-brain-52
