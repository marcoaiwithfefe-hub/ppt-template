Reviewed 45d803f against c49de09 through pinned code, existing tests and saved evidence. No tests rerun or new probes constructed. All citations below refer to 45d803f.

F16 | MAJOR | src/deckfill/web.py:26-36,109-114,136-140
Repeated-heading edits can still transfer a pick to another slide without its note. Example: two content slides titled Status, with different bodies. Pick a layout for first, then delete or rename first. Surviving second becomes occurrence 0 and inherits that pick. No layout_gone appears because occurrence 0 still exists. Conversely, picking second and deleting first drops surviving slide's pick because occurrence 1 disappears. Page retains remapped picks at docs/app.js:282; download repeats same matching. Implementation follows D1's prescribed title/kind/nth key, but that key cannot satisfy revision 6's promises about repeated titles, deletion above a picked slide and title edits. Fix: reconcile against previous slide identities; when identity is ambiguous, warn and drop affected picks rather than silently transfer them. Align D1's identity rule with C2's promised behavior. Add cases that edit membership of a repeated-heading group and assert both UI and downloaded layouts. Existing repeated-title test inserts only a differently named slide (tests/test_web_bridge.py:80-92); browser test uses unique titles throughout (tests/e2e/override_follow.mjs:16-18,79-107). Likelihood: uncommon ordinary edit involving repeated headings. Finding follows inspected code; no probe run.

Other focus checks: no normal-path stale_plan regression found. Plan retains requested overrides, and fill recomputes from those same inputs (src/deckfill/plan.py:286-292; src/deckfill/fill.py:306-310). Bridge fill creates a fresh plan from current picks (src/deckfill/web.py:131-140). Page stores returned surviving picks and renders sources, selections and warnings from the same accepted result (docs/app.js:272-283,311-329,344-352). Both new warning strings match C19 proof-list entries (docs/copy.js:114-115; qa/c19/PROOF-LIST.md:10-11).

Prior evidence gaps: C14 now has a dated, source-attributed comparison of documented requirements (qa/c14/google-format.md:3-23,34-36). G0 now records named, dated visual review tied to render hashes, satisfying its specified seat-eye evidence method (qa/g0/G0-RESULT.md:9-12,49-58; qa/g0/report.json:13-59). I did not independently fetch those pages or inspect those renders this round.

New findings only: BLOCKER 0, MAJOR 1, MINOR 0, NICE 0.
Ship readiness: 8/10 within this round's scope. F16 keeps C2 open.
Confidence: 9/10 on inspected code and test conclusions.

Need from you: nothing needed.
