Reviewed requested diff and pinned 0a0a0cc code. No tests rerun or new probes constructed.

F17 | MINOR | 0a0a0cc:docs/copy.js:114
New layout_gone message does not describe every cause. It lists deletion, title changes and changes in number of same-titled slides. Changing slide kind also drops a pick: adding first bullet to a section changes it to content while title and number of same-titled slides remain unchanged (src/deckfill/outline.py:131-138). Old title/kind key then has no match and emits layout_gone (src/deckfill/web.py:35-40,121). Fix: include content/type changes, or use neutral wording explaining that previous pick could not be retained. Likelihood: ordinary outline edit. Wording only; cancellation and warning still work.

No new behavior regression found within revision 7's count-change rule. Bridge counts outline slides by title and kind, returns count in sources and surviving picks, and page stores it (0a0a0cc:src/deckfill/web.py:44-54,102-119; docs/app.js:282,323-329). Unique-title pick remains valid when count stays one; existing test checks insertion above it and downloaded layout (tests/test_web_bridge.py:65-81). Plan and fill use same placement function, and fill verifies a freshly generated plan, so no normal-path stale_plan disagreement found (src/deckfill/web.py:96-98,143-147; src/deckfill/fill.py:306-310).

New findings only: BLOCKER 0, MAJOR 0, MINOR 1, NICE 0.
Ship readiness: 9/10 within this round's scope.
Confidence: 9/10.

Need from you: nothing needed.
