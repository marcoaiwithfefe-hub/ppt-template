# Build checklist

- [x] deckfill module: read_template, parse_outline, plan_deck, fill
- [x] fixture templates by script (fixtures/make_fixtures.py), rels-order added at G0
- [x] CPython tests: C1, C2, C3, C4, C5 (integrity part), C6, C7, C8, C11 (169 pass at 6d430ea)
- [ ] C5 validator: Open XML SDK console tool in tools/validate (code written; BLOCKED: dotnet SDK install refused by the permission classifier, needs Marco)
- [ ] G0: 5 real templates, renders, verdict (4 of 5 clean, validator part NOT RUN; qa/g0/G0-RESULT.md)
- [ ] Page: docs/, Cantonese copy file, Mentron look, CSP and lockdown
- [x] Pyodide self-hosted and pinned (314.0.7)
- [x] PROMPT.md, skill/ppt-outline/SKILL.md, README.md, LICENSE (README and page copy wait on Marco's Rule 25 proof)
- [ ] End-to-end (Playwright): C8 page part, C9, C10, C12, C13
- [ ] C14 copy floors, C15 Gemini outlines (C15 3 of 3 pass; C14 waits on the page)
- [ ] D10 demo deck and renders
- [ ] Failure demos for C1, C2, C4, C5, C9 in qa/failure-demos/
- [ ] Slop scan triage
- [ ] blast-radius: privacy proof from a saved request log
- [ ] Walkthrough rendered to qa/walkthrough/
- [ ] Report to ai-brain-52
