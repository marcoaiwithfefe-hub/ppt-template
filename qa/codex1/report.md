Reviewed pinned application code and evidence. Application files under src/ and docs/ have identical Git blobs at 884f33a and f6c30a9. Walkthrough artifact is available at f6c30a9:qa/walkthrough/walkthrough.json:1, but absent at 884f33a; its claims were checked against 884f33a. Known cap/heap changes and missing .NET execution excluded. No files changed. Targeted probes ran pinned code in memory; full browser suite was not rerun.

F1 | BLOCKER | [diff] | f6c30a9:docs/app.js:232-235,333-337
Download can silently omit latest edits. Input schedules replanning 450 ms later while previous plan remains downloadable. Download calls Session.fill() against cached plan (f6c30a9:src/deckfill/web.py:80-81). Pinned-JS probe changed textarea to NEW CONTENT and immediately downloaded OLD CONTENT. Fix: invalidate download synchronously on input and await planning of current outline and overrides before filling. Likelihood: ordinary edit or paste followed by immediate download.

F2 | MAJOR | [diff] | f6c30a9:src/deckfill/package.py:60-62,92-95,106-120,282-285
XML security checks depend on filename extension. A slide-layout XML part renamed to .dat, with relationships and content type updated, bypasses XML-specific caps and DOCTYPE rejection. Pinned-engine probes accepted both an oversized XML layout and a DOCTYPE containing an entity declaration. No entity expansion or disclosure observed. Fix: identify XML through OPC content types as well as relationship filenames, then enforce byte limits and safe parsing before python-pptx opens it. Likelihood: crafted malicious template; uncommon accidental input.

F3 | MAJOR | [diff] | f6c30a9:src/deckfill/package.py:81-86
Member limit runs after central-directory allocation. ZipFile constructs every ZipInfo before code checks the 2,000-member cap. A 47,000,053-byte crafted archive containing 1,000,000 central-directory records eventually raised too_big, but CPython process peak RSS reached 510.4 MiB, versus 162.6 MiB before parsing. This is separate from excluded accepted-input heap changes. Fix: bounded central-directory preflight before ZipFile construction, including actual record count and ZIP64/count inconsistencies. Likelihood: adversarial archive; browser memory impact was not measured.

F4 | MAJOR | [diff] | f6c30a9:src/deckfill/plan.py:158-164
Long-word wrapping can monopolize main thread. Width is subtracted repeatedly from token width; a tiny positive usable box width remains accepted (f6c30a9:src/deckfill/template.py:266-272). With normal 20-point text and 1 EMU usable width, 50 characters required about 7 million iterations. A near-limit outline implies billions; full browser duration was not measured. Fix: calculate line count and remainder with constant-time arithmetic, and test tiny widths. Likelihood: adversarial or damaged placeholder geometry.

F5 | MAJOR | [claims] | f6c30a9:src/deckfill/package.py:238-266
Integrity check misses package-root relationships. It skips _rels/.rels and never validates all relationships from source "". Probe added a root relationship targeting missing.xml; check_integrity returned no problems and read_template accepted it. Fix: validate root targets and external URIs alongside part relationships. Spec L149: "every internal relationship target resolves to a part in the package". Likelihood: damaged or crafted template.

F6 | MAJOR | [claims] | f6c30a9:src/deckfill/fill.py:73-86
Removing sample slides can make otherwise accepted templates unfillable. Generic XML parts, including viewProps.xml, lack _element. Code removes their slide relationships but leaves XML references intact. A saved outline-view reference passed input integrity, then fill raised "bad_file: output failed integrity: id=rId1 names no relationship in ppt/viewProps.xml". Fix: safely parse and update generic XML blobs when removing references. Spec L150: "Any element in a kept part whose relationship points to a removed slide ... is removed together with that relationship." Likelihood: uncommon saved outline-view state. Synthetic case was not SDK-validated.

F7 | MAJOR | [claims] | f6c30a9:src/deckfill/plan.py:245-247
Subtitle-to-body fallback bypasses fit checks. Title slides receive unconditional fits even when subtitle targets a content body. A 4,000-character subtitle overridden onto a content layout produced one slide, fits, and no warning. Fix: estimate subtitle paragraphs when their destination is a body and return warned/check status as appropriate. Spec L165: "For each body, plan_deck estimates the text height". Likelihood: supported fallback or override with long subtitle.

F8 | MAJOR | [spec] | f6c30a9:src/deckfill/fill.py:147-160
Positioned slide-local footers disappear. Code finds an example footer, then discards it if destination layout lacks that footer placeholder, even when source footer has explicit geometry. Pinned-engine probe lost LOCAL FOOTER text without warning. Fix: preserve positioned source footer and resolve geometry where needed. Spec L155: "Input slides on the same layout: if one carries the type, the new slide gets it, copied from the first such slide". Likelihood: uncommon customized corporate template.

F9 | MAJOR | [diff] | f6c30a9:docs/app.js:401-409,423-428
Prompt-load failure leaves an apparently ready page copying empty text. Boot swallows fetch rejection and loads engine anyway; copy closure remains empty. Retry updates displayed prompt but never updates that closure. HTTP errors are also not checked (f6c30a9:docs/app.js:126-129). Fix: disable copying until prompt loads successfully, surface failures, check response status, and use same setter on retry. Likelihood: intermittent initial resource failure.

F10 | MAJOR | [spec] | f6c30a9:tests/e2e/c9_privacy.mjs:237-249
C9 PASS lacks required session coverage. Saved ready-to-link interval is only 5.247 seconds (f6c30a9:qa/e2e/c9-report.json:143-164), contradicting claimed 30-second idle coverage. Mutation runner sets IDLE_MS=3000 and overwrites same report (f6c30a9:qa/failure-demos/run_demos.py:74-78). Only Mentron link was recorded; test swallows click failures and requires merely one link-out. Fix: separate mutation evidence, assert elapsed idle duration, preserve page while testing links, require all three anchors, and record tested commit/input hashes. Spec L221: "30 s idle after the last download, clicking each link-out (intercepted, not followed)". No leak demonstrated.

F11 | MAJOR | [spec] | f6c30a9:tests/oracle.py:230-250
C3 exempts whole parts containing removed-slide hyperlinks. Unrelated decoration damage in those parts escapes comparison. In-memory probe of pinned oracle deleted all content from such a layout and still returned no problems. Fix: normalize only authorized hyperlink elements and relationships, then compare remaining XML. Spec L151: "Every other part is kept: binary parts byte for byte, XML parts equal after canonicalisation". This proves test weakness, not actual logo deletion by fill.

F12 | MAJOR | [spec] | f6c30a9:qa/g0/run_g0.py:150-159
G0's placeholder-only result is hardcoded true and excluded from script_clean. Shared reader ignores non-placeholder text shapes (f6c30a9:tests/oracle.py:127-134), so extra text outside placeholders can evade claimed check. Fix: inspect every text-bearing output shape and include result in gate. Spec L212: "every text in a placeholder".

F13 | MAJOR | [spec] | f6c30a9:qa/c5/run_validator.py:60-76
Validator runner silently omits missing required outputs. G0 decks are discovered by glob; C10 downloads are included only when present. Both are gitignored, so validation can report success without either family. Fix: require explicit artifact manifest, fail incomplete runs, and cover all output families claimed by C5. Spec L217: "reports zero errors on every output". This finding concerns runner behavior, not excluded SDK installation.

F14 | MAJOR | [spec] | f6c30a9:qa/gemini/check_c15.py:41,60-77
C15 checker can succeed with missing cases or changed numbers. It skips absent outputs, accepts numeric substrings such as 14 inside 114, and exits successfully after printing FAIL. Fix: require three named cases, compare numeric tokens, and exit nonzero on failure. Spec L227: "on three notes" and "keeps every number from the notes". Current saved report contains three passing cases; no current numeric loss established.

Evidence limits: G0 visual judgments reference untracked renders (f6c30a9:qa/g0/G0-RESULT.md:39-47). C10 reports two equal outputs, but browser artifacts are untracked and report lacks hashes (f6c30a9:qa/e2e/c9-report.json:145-158; f6c30a9:qa/e2e/c10-report.json:1-14). These measurements cannot be independently reconstructed from pinned artifacts. C12's recorded warm result is 4.985 seconds, within its bar, not a rounded failure (f6c30a9:qa/e2e/c12-report.json:47-50).

Confidence: 9/10 on reported code defects and check weaknesses. Need from you: nothing needed for this review.
BLOCKER 1, MAJOR 13, MINOR 0, NICE 0. Ship readiness after known items close: 4/10.
