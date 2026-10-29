# Blast radius: d97256c to HEAD

## What it does

A static page in `docs/` loads Pyodide, python-pptx and `deckfill` from its own origin, then locks the network by adding a second Content Security Policy (`connect-src 'none'; img-src data: blob:; worker-src 'none'`). The user's template, outline and deck stay in the tab: `deckfill.web.Session` reads, plans and fills on the main thread, and the deck leaves as a `blob:` download.

The parts the diff does not spell out:
- `fill` re-zips every output and puts the template's own bytes back for every kept part whose meaning is unchanged (`src/deckfill/fill.py`, `_restore_kept`). It also writes each slide's own number into copied slide-number fields.
- The page reaches Python through a hook on `window` only when the URL hash is `#e2e` (`docs/app.js`, in `loadEngine`).

## The one fact it is safe because of

After ready, the page makes no request of any kind. Proven at step 4 (ran real code) on HEAD `fc505ff`.

`node tests/e2e/c9_privacy.mjs` drives the real page in headless Chromium and saves every browser request and every server hit with times (`qa/e2e/c9-report.json`). The session covers open, ready, two fills with downloads (one with a layout override), reset, 30 s idle, an offline fill and a click on each link-out. `qa/e2e/privacy_proof.py` reads that saved log:

```
session 33 s; 20 browser requests, 19 server hits
before ready: 19 requests, 0 to another origin
after ready: 1 browser requests, of which 1 are clicked link-outs (https://mentron.hk/)
after ready: 0 page requests, 0 server hits, 0 blocked attempts
fills after ready: 2 with downloads, plus one offline
PASS: zero page requests after ready
```

It also fails when it should. The two C9 mutations (a same-origin fetch one second after each download, and outline text in the Gemini link) both fail the session (`qa/failure-demos/c9-*-mutated.txt`). After ready, `fetch` from page JS and from Python (`js.fetch`, `pyodide.http.pyfetch`), same origin and other origin, and new workers (URL, `blob:`, `data:`) are all blocked by the browser.

## Risks

- **Memory at the input caps.** At the D1b worst case (49.8 MB file, 284 MB uncompressed), the wasm heap reached 2.39 GB, and wasm memory never shrinks. On a low-memory office laptop the tab could crash. The cost is a lost session, not a leak. Likelihood is low: real templates in G0 were 0.3 to 15 MB, and HKUST template 14 (73.7 MB) took the heap from 45 to 471 MB to read. Check: `node tests/e2e/c12_load.mjs` prints `wasmHeapMB`. Evidence: `qa/e2e/c12-report.json`.
- **GitHub Pages MIME types and headers.** Not proven locally. The page needs `application/wasm` for `pyodide.asm.wasm` and a JavaScript type for `.mjs`. Check at the deploy gate: Fable's real-Chrome run on the Pages URL (root Rule 127). Likelihood low (Pages serves both types), cost high (page never reaches ready, so it fails closed, with no leak).
- **Warm load sits on its bar.** The second visit took 5.0 s against 5 s, because the headless test profile's memory cache does not keep the 9.6 MB wasm. A real Chrome profile has a disk cache. Check in real Chrome at the deploy gate.

## Cleared

- **Subpath.** Pages serves the site at `/ppt-template/`. A scratch server mounted `docs/` there: ready, fill and download all worked, 19 requests all inside `/ppt-template/`, 0 after ready. Every page URL is relative (`new URL("./", location.href)` in `docs/app.js`; `fonts/...` in `docs/style.css`).
- **Pyodide's default CDN.** `pyodide.mjs` falls back to jsdelivr when `packageBaseUrl` is unset. `app.js` sets it to the vendor folder, and the static origin check allowlists only that string, with the reason.
- **Lazy loads after ready.** All Python modules are imported before the lockdown. A missing module would raise, not fetch. The 2 fills plus 1 offline fill after ready made 0 requests. Each font family is one file, loaded through `document.fonts.load` before ready. User text outside the Noto Serif TC subset falls back to a system font, with no request.
- **`_restore_kept` restoring a part the fill meant to change.** Every intended change is excluded by name (the presentation part and its `.rels`, `[Content_Types].xml`, `docProps/app.xml`) or by content type (slide and notes parts). Otherwise it differs in meaning (a layout `.rels` or XML with a hyperlink to a removed slide), so it is not restored. C3 on `sections` checks the hyperlink removal survives. 173 tests pass. The isolated mutation demo is `qa/failure-demos/c3-rels-order-*.txt`.
- **The `#e2e` hook.** It exposes the page's own Pyodide to the page's own window. It adds no request (the hash never reaches a server) and no new reader of the user's data.
- **Download names.** `file_name` strips Windows-unsafe characters and collapses spaces (`tests/test_web_bridge.py`). Windows reserved device names (`CON`) are left to Chrome's own download-name rules. Unproven, low cost: the user renames the file.
- **Other browsers.** The spec targets Chrome and Edge on Windows. Firefox and Safari behaviour of a CSP meta added after load was not tested.

## Before you merge

- `node tests/e2e/c9_privacy.mjs && .venv/bin/python qa/e2e/privacy_proof.py` on the commit that ships.
- `node tests/e2e/c12_load.mjs` for the memory and timing numbers.
- At deploy: the Pages URL in real Chrome, ready and one fill, with DevTools Network open after ready.
