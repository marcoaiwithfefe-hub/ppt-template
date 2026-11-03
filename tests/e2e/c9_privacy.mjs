// C9 privacy, C8 page part, C10 downloads, C13 phone: the page in headless Chromium on a local
// static server. One browser context logs every request for the whole session.
// Rev 9: the whole session runs twice, on a Mac user agent and on a Windows one (C39 page part: the page picks the
// Chinese face from it), and each run checks the first-draft line after its downloads (C45).
// Run: node tests/e2e/c9_privacy.mjs   (report: qa/e2e/c9-report.json, exit 1 on any failure)
// E2E_OUT=<dir> writes the report and downloads there instead (failure demos use it, so a mutated
// run never overwrites the evidence run).
import { chromium } from "playwright-core";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { inflateRawSync } from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = process.env.E2E_OUT ? path.resolve(process.env.E2E_OUT) : path.join(ROOT, "qa", "e2e");
const FIX = path.join(ROOT, "fixtures", "out");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const IDLE_MS = 30000; // spec C9: 30 s idle after the last download, asserted from measured times
const REQUIRED = {
  "default-src": ["'self'"], "connect-src": ["'self'"], "form-action": ["'none'"],
  "base-uri": ["'none'"], "object-src": ["'none'"], "script-src": ["'self'", "'wasm-unsafe-eval'"],
};

// rev 9: one session per user agent; T1 gives Chinese text PingFang HK on Mac, iPhone and iPad, else Microsoft JhengHei
const AGENTS = [
  { tag: "mac", face: "PingFang HK",
    ua: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36" },
  { tag: "windows", face: "Microsoft JhengHei",
    ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36" },
];
const COPY = (await import(path.join(ROOT, "docs", "copy.js"))).COPY;
const fmt = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k]));
const HAN = /[\u3400-\u4DBF\u4E00-\u9FFF\u{20000}-\u{323AF}]/u;

const checks = [];
let RUN = ""; // the user agent of the session under way; its checks carry it in their names
const check = (id, name, ok, detail = "") => checks.push({ id, name: RUN ? `(${RUN}) ${name}` : name, ok: !!ok, detail });

// ------------------------------------------------------------------ static: every HTML page's policy
function parsePolicy(content) {
  const map = {};
  for (const part of content.split(";")) {
    const [name, ...vals] = part.trim().split(/\s+/);
    if (name) map[name.toLowerCase()] = vals;
  }
  return map;
}

async function htmlFiles(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...(await htmlFiles(p)));
    else if (e.name.endsWith(".html")) out.push(p);
  }
  return out;
}

async function staticPolicy() {
  for (const file of await htmlFiles(path.join(ROOT, "docs"))) {
    const html = await readFile(file, "utf8");
    const metas = [...html.matchAll(/<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"/gi)];
    const pol = metas.length ? parsePolicy(metas[0][1]) : {};
    const missing = Object.entries(REQUIRED).filter(([k, v]) => JSON.stringify(pol[k]) !== JSON.stringify(v));
    const firstInHead = /<head>\s*<meta charset="utf-8">\s*<meta http-equiv="Content-Security-Policy"/i.test(html);
    check("C9", `base policy in ${path.relative(ROOT, file)}`, metas.length === 1 && !missing.length && firstInHead,
      missing.map(([k]) => k).join(" "));
  }
}

// ------------------------------------------------------------------ static: no resource from another origin
// Our own files may name another origin only in a plain <a href>. Vendor files may name one only
// where listed here with the reason it is never requested (the session's request log is the proof).
const VENDOR_ALLOW = {
  "docs/vendor/pyodide/pyodide.mjs": ["https://cdn.jsdelivr.net", "Pyodide's default package CDN; app.js sets packageBaseUrl"],
  "docs/vendor/pyodide/pyodide.asm.mjs": ["http://github.com", "text inside an error message"],
  "docs/vendor/pyodide/package.json": ["https://github.com", "npm metadata (repository, bugs, homepage); the page never fetches this file"],
};

async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(p)));
    else out.push(p);
  }
  return out;
}

async function staticOrigins() {
  const bad = [];
  for (const file of await walk(path.join(ROOT, "docs"))) {
    const rel = path.relative(ROOT, file);
    if (/\.(woff2|wasm|zip|whl|png|ico)$/.test(rel) || /OFL-[\w-]+\.txt$/.test(rel)) continue;
    let text = await readFile(file, "utf8");
    if (rel === "docs/index.html") text = text.replace(/<a\s[^>]*href="https?:[^"]*"/g, "<a");
    const found = [...new Set([...text.matchAll(/(?:https?:)?\/\/[a-z0-9][a-z0-9.-]*\.[a-z]{2,}/gi)].map((m) => m[0]))];
    const allowed = VENDOR_ALLOW[rel];
    for (const origin of found) if (!allowed || !origin.startsWith(allowed[0])) bad.push(`${rel}: ${origin}`);
  }
  check("C9", "no file under docs/ names another origin for a resource", !bad.length, bad.join(" "));
}

// ------------------------------------------------------------------ the session
const INIT = () => {
  window.__made = [];
  window.__violations = [];
  for (const name of ["Worker", "SharedWorker"]) {
    const Orig = window[name];
    if (!Orig) continue;
    window[name] = function (...args) { window.__made.push(name); return new Orig(...args); };
  }
  document.addEventListener("securitypolicyviolation", (e) =>
    window.__violations.push({ dir: e.violatedDirective, uri: e.blockedURI, t: Date.now() }));
  new MutationObserver((ms) => {
    for (const m of ms) for (const n of m.addedNodes) if (n.nodeName === "IFRAME") window.__made.push("iframe");
  }).observe(document, { childList: true, subtree: true });
};

async function waitReady(page) {
  await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 120000 });
}

// step 3's rev 9 lines: the face line (T1) and the first-draft line under `downloaded` (T7)
async function lines(page) {
  return page.evaluate(() => {
    const d = document.getElementById("downloaded");
    const r = document.getElementById("refine-note");
    const f = document.getElementById("cjk-face");
    return {
      route: document.getElementById("route-sample").getAttribute("aria-pressed") === "true" ? "sample" : "layout",
      downloaded: !d.hidden && d.checkVisibility(),
      refine: !r.hidden && r.checkVisibility(),
      under: d.nextElementSibling === r && r.getBoundingClientRect().top >= d.getBoundingClientRect().bottom,
      refineText: r.textContent,
      face: !f.hidden && f.checkVisibility(),
      faceText: f.textContent,
    };
  });
}

// C45: hidden before the download; after it, shown under `downloaded` with the copy of record byte for byte
function checkRefine(label, route, pre, post) {
  check("C45", `${label} (${route} route): the first-draft line hidden before the download, under the downloaded line after it, text of record`,
    pre.route === route && post.route === route && !pre.refine && !pre.downloaded && post.downloaded && post.refine && post.under &&
      post.refineText === COPY.refineNote, JSON.stringify({ pre, post }));
}

// a zip's parts by name (stored or deflated entries)
function unzip(buf) {
  const eocd = buf.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const out = {};
  let p = buf.readUInt32LE(eocd + 16);
  for (let i = buf.readUInt16LE(eocd + 10); i > 0; i--) {
    const method = buf.readUInt16LE(p + 10);
    const size = buf.readUInt32LE(p + 20);
    const nameLen = buf.readUInt16LE(p + 28);
    const local = buf.readUInt32LE(p + 42);
    const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
    const data = buf.subarray(start, start + size);
    out[buf.toString("utf8", p + 46, p + 46 + nameLen)] = method === 8 ? inflateRawSync(data) : data;
    p += 46 + nameLen + buf.readUInt16LE(p + 30) + buf.readUInt16LE(p + 32);
  }
  return out;
}

async function fillOnce(page, tpl, outline, label, overrideIndex) {
  await page.setInputFiles("#file", tpl);
  await page.waitForSelector("#layouts:not([hidden])");
  await page.fill("#outline", outline);
  await page.waitForSelector("#plan:not([hidden])");
  await page.waitForFunction(() => document.getElementById("working").hidden);
  let override = null;
  if (overrideIndex != null) {
    const sel = page.locator("#slides select").nth(overrideIndex);
    const values = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    const current = await sel.inputValue();
    const next = values.find((v) => v !== current);
    if (next) {
      await sel.selectOption(next);
      await page.waitForFunction(() => document.getElementById("working").hidden);
      override = next;
    }
  }
  const pre = await lines(page);
  check("C39", `${label} (layout route): no face line`, pre.route === "layout" && !pre.face, JSON.stringify(pre));
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#download")]);
  const tDownload = Date.now();
  const file = path.join(OUT, `${label}.pptx`);
  await dl.saveAs(file);
  await page.waitForFunction(() => !document.getElementById("downloaded").hidden);
  checkRefine(label, "layout", pre, await lines(page));
  return { file, name: dl.suggestedFilename(), override, overrideSource: override ? overrideIndex : null, tDownload };
}

async function sampleRoute(page, agent) {
  const copy = (await import(path.join(ROOT, "docs", "copy.js"))).COPY;
  const outlineRel = "tests/outlines/sample/design.md";
  const outline = await readFile(path.join(ROOT, outlineRel), "utf8");
  await page.setInputFiles("#file", path.join(FIX, "sample-design.pptx"));
  await page.waitForSelector("#layouts:not([hidden])");
  const route = await page.evaluate(() => ({
    shown: !document.getElementById("route").hidden && !document.getElementById("route-switch").hidden,
    line: document.getElementById("route-line").textContent,
    sample: document.getElementById("route-sample").getAttribute("aria-pressed"),
  }));
  check("C22", "both routes on offer: the route line and switch show, sample pressed",
    route.shown && route.sample === "true" && route.line.startsWith(copy.routeLineSample.split("{")[0]), JSON.stringify(route));
  await page.fill("#outline", outline);
  await page.waitForSelector("#plan:not([hidden])");
  // the plan for this outline is in only when download is enabled again: the template read re-plans the previous
  // outline first, and the new outline's plan comes after a 450 ms pause (reading rows before it races, QA round 1)
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  const options = await page.$$eval("#slides select", (sels) => sels.map((s) => [...s.options].map((o) => [o.value, o.textContent])));
  const okLabels = options.every((opts) => opts.every(([v, t]) => /^s\d+$/.test(v) && t.startsWith("範本頁 " + v.slice(1))));
  const compatible = { 0: ["s1", "s2", "s3", "s4", "s5", "s6"], 1: ["s2", "s3", "s4", "s5", "s6"] };
  const okCompat = JSON.stringify(options[1].map(([v]) => v)) === JSON.stringify(compatible[1]);
  check("C31", "the picker lists only compatible samples as 範本頁 k plus first words", okLabels && okCompat, JSON.stringify(options.slice(0, 2)));
  // picks on outline slides 1 and 4, each a re-plan
  const overrides = {};
  for (const [idx, value] of [[1, "s6"], [4, "s5"]]) {
    await page.locator("#slides select").nth(idx).selectOption(value);
    await page.waitForFunction(() => !document.getElementById("download").disabled);
    overrides[idx] = value;
  }
  const chosen = await page.$$eval("#slides select", (sels) => sels.map((s) => s.value));
  check("C31", "choosing a sample re-plans with it", chosen[1] === "s6" && chosen[4] === "s5", chosen.join(" "));
  const pre = await lines(page);
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#download")]);
  const tDownload = Date.now();
  const file = path.join(OUT, `c28-sample-design-${agent.tag}.pptx`);
  await dl.saveAs(file);
  await page.waitForFunction(() => !document.getElementById("downloaded").hidden);
  checkRefine("c28-sample-design", "sample", pre, await lines(page));
  // switch to layouts: a re-plan, both picks dropped with a note each, the picker now lists layouts
  await page.click("#route-layout");
  await page.waitForFunction(() => document.getElementById("working").hidden);
  const after = await page.evaluate(() => ({
    pressed: document.getElementById("route-layout").getAttribute("aria-pressed"),
    notes: [...document.querySelectorAll("#warnings-list li")].map((li) => li.textContent),
    first: document.querySelector("#slides select")?.value || "",
    lines: [document.getElementById("downloaded").hidden, document.getElementById("refine-note").hidden],
  }));
  check("C45", "the route switch hides the first-draft line with the downloaded line", after.lines.every(Boolean), JSON.stringify(after.lines));
  const gone = after.notes.filter((t) => t.includes(copy.warnings.layout_gone.split("「")[0]) || t.includes("取消咗")).length;
  check("C22", "switching to layouts re-plans and drops both picks with a note each",
    after.pressed === "true" && gone === 2 && after.first.startsWith("/ppt/slideLayouts/"), JSON.stringify(after));
  await page.click("#route-sample");
  await page.waitForFunction(() => document.getElementById("working").hidden);
  // code review E2: a pick, then an empty outline, a switch away and back, the outline again: the pick stays gone
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  const auto = await page.$$eval("#slides select", (sels) => sels.map((s) => s.value));
  const other = options[1].map(([v]) => v).find((v) => v !== auto[1]);
  await page.locator("#slides select").nth(1).selectOption(other);
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  await page.fill("#outline", "");
  await page.waitForFunction(() => document.getElementById("plan").hidden);
  await page.click("#route-layout");
  await page.waitForFunction(() => document.getElementById("working").hidden);
  await page.click("#route-sample");
  await page.waitForFunction(() => document.getElementById("working").hidden);
  await page.fill("#outline", outline);
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  const back = await page.evaluate(() => ({
    first: document.querySelectorAll("#slides select")[1]?.value || "",
    notes: [...document.querySelectorAll("#warnings-list li")].map((li) => li.textContent),
  }));
  const noted = back.notes.filter((t) => t.includes(copy.warnings.layout_gone.split("「")[0]) || t.includes("取消咗")).length;
  check("C22", "a pick made before an empty outline and a route round trip stays gone, with its note",
    back.first === auto[1] && back.first !== other && noted === 1, JSON.stringify({ auto: auto[1], other, ...back }));
  return { template: "sample-design.pptx", outline: outlineRel, route: "sample", overrides, file, name: dl.suggestedFilename(), tDownload };
}

// rev 9 (C39 page part): sample-latin-font on the sample route. A Chinese outline: step 3 names the face the page
// picked from its user agent, and the downloaded slides carry it in a:ea on Chinese runs (the other face nowhere).
// An English-only outline: no face line.
async function faceRoute(page, agent) {
  const outlineRel = "tests/outlines/sample/latin-font.md";
  const outline = await readFile(path.join(ROOT, outlineRel), "utf8");
  await page.setInputFiles("#file", path.join(FIX, "sample-latin-font.pptx"));
  await page.waitForSelector("#layouts:not([hidden])");
  await page.fill("#outline", outline);
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  const shown = await lines(page);
  check("C39", `sample-latin-font (sample route), Chinese outline: step 3 names ${agent.face}`,
    shown.route === "sample" && shown.face && shown.faceText === fmt(COPY.cjkFaceNote, { face: agent.face }), JSON.stringify(shown));
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#download")]);
  const tDownload = Date.now();
  const file = path.join(OUT, `c39-latin-font-${agent.tag}.pptx`);
  await dl.saveAs(file);
  const slides = Object.entries(unzip(await readFile(file)))
    .filter(([n]) => /^ppt\/slides\/slide\d+\.xml$/.test(n)).map(([, b]) => b.toString("utf8"));
  const runs = slides.flatMap((x) => x.match(/<a:r>[\s\S]*?<\/a:r>/g) || []);
  const chinese = runs.filter((r) => HAN.test((r.match(/<a:t(?:\s[^>]*)?>([^<]*)<\/a:t>/) || ["", ""])[1]));
  const withFace = chinese.filter((r) => r.includes(`<a:ea typeface="${agent.face}"`));
  const other = AGENTS.find((a) => a !== agent).face;
  const elsewhere = slides.filter((x) => x.includes(`typeface="${other}"`)).length;
  check("C39", `the download's slides carry ${agent.face} in a:ea on Chinese runs, ${other} nowhere`,
    slides.length > 0 && withFace.length > 0 && !elsewhere,
    `${slides.length} slides, ${withFace.length} of ${chinese.length} Chinese runs in ${agent.face}, ${elsewhere} slides naming ${other}`);
  await page.fill("#outline", await readFile(path.join(ROOT, "tests", "outlines", "english.md"), "utf8"));
  await page.waitForFunction(() => !document.getElementById("download").disabled);
  const english = await lines(page);
  check("C39", "sample-latin-font (sample route), English-only outline: no face line",
    english.route === "sample" && !english.face && !english.faceText, JSON.stringify(english));
  return { template: "sample-latin-font.pptx", outline: outlineRel, route: "sample", file, name: dl.suggestedFilename(), tDownload };
}

async function session(browser, agent) {
  const { server, log, port } = await startServer();
  const origin = `http://127.0.0.1:${port}`;
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true, userAgent: agent.ua });
  await ctx.addInitScript(INIT);
  const reqs = [];
  const linkOuts = [];
  await ctx.route("**/*", (route) => {
    const u = route.request().url();
    if (u.startsWith(origin) || u.startsWith("data:") || u.startsWith("blob:")) return route.continue();
    linkOuts.push({ t: Date.now(), url: u, nav: route.request().isNavigationRequest() });
    // 204 No Content: the browser stays on the page, so every link can be clicked in turn
    return route.fulfill({ status: 204, body: "" });
  });
  ctx.on("request", (r) => reqs.push({ t: Date.now(), url: r.url(), type: r.resourceType() }));
  const page = await ctx.newPage();
  const outline = await readFile(path.join(ROOT, "fixtures", "reference-outline.md"), "utf8");

  await page.goto(`${origin}/#e2e`);
  await waitReady(page);
  const tReady = Date.now();
  const ua = await page.evaluate(() => navigator.userAgent);
  check("C39", `the page runs on the ${agent.tag} user agent`, ua === agent.ua, ua);
  const before = reqs.filter((r) => r.t <= tReady);
  check("C9", "before ready: only the page origin",
    before.every((r) => r.url.startsWith(origin) || r.url.startsWith("data:")), before.filter((r) => !r.url.startsWith(origin)).map((r) => r.url).join(" "));

  const fills = [];
  fills.push({ template: "wui-tung.pptx", ...(await fillOnce(page, path.join(FIX, "wui-tung.pptx"), outline, `c10-wui-tung-${agent.tag}`)) });
  fills.push({ template: "typed.pptx", ...(await fillOnce(page, path.join(FIX, "typed.pptx"), outline, `c10-typed-override-${agent.tag}`, 1)) });

  // rev 8: the sample route, offline (C22 page part, C28, C31): route line and switch, the 範本頁 picker,
  // picks on two slides, a download with the route and every pick recorded, then a switch to layouts that drops both
  await ctx.setOffline(true);
  fills.push(await sampleRoute(page, agent));
  fills.push(await faceRoute(page, agent));
  await ctx.setOffline(false);

  // offline after ready: a fill still downloads. It runs before the idle, and the network is back
  // on for the idle, so the session's last download is followed by 30 s in which any delayed
  // request could reach the server (Codex round 2, F10)
  await ctx.setOffline(true);
  const off = await fillOnce(page, path.join(FIX, "wui-tung.pptx"), outline, `offline-${agent.tag}`);
  check("C9", "offline after ready: a fill still downloads", off.name.endsWith(".pptx"));
  await ctx.setOffline(false);

  const tDownloads = [...fills, off].map((f) => f.tDownload);
  const tLastDownload = Math.max(...tDownloads);
  const tIdleStart = Date.now();
  await page.click("#reset");
  await page.waitForTimeout(IDLE_MS);
  const tIdleEnd = Date.now();
  const idleRequests = reqs.filter((r) => r.t > tLastDownload && r.t <= tIdleEnd);
  const idleHits = log.filter((l) => l.t > tLastDownload && l.t <= tIdleEnd);
  check("C9", `idle starts after the session's last download (${tDownloads.length} downloads)`, tIdleStart >= tLastDownload);
  check("C9", `idle after the last download ${((tIdleEnd - tIdleStart) / 1000).toFixed(1)} s (at least 30), no request in it`,
    tIdleEnd - tIdleStart >= IDLE_MS && !idleRequests.length && !idleHits.length,
    [...idleRequests.map((r) => r.url), ...idleHits.map((l) => l.path)].join(" "));

  const made = await page.evaluate(() => window.__made.slice());
  const violations = await page.evaluate(() => window.__violations.slice());
  check("C9", "no Worker, shared worker or iframe in the session", !made.length && page.frames().length === 1 && !ctx.serviceWorkers().length, made.join(" "));
  check("C9", "no CSP violation in the session (nothing tried the network)", !violations.length, JSON.stringify(violations));

  // probes: page JS, Python, Worker, all after ready, all must be blocked
  const probes = await page.evaluate(async () => {
    const out = {};
    const tryFetch = async (u) => { try { await fetch(u); return "allowed"; } catch { return "blocked"; } };
    out.jsSame = await tryFetch("/copy.js?probe");
    out.jsOther = await tryFetch("https://example.com/probe");
    // a worker counts as allowed only if its script runs and posts back
    const runs = (make) => new Promise((resolve) => {
      let w;
      try { w = make(); } catch { return resolve("blocked"); }
      const done = (v) => { clearTimeout(timer); w.terminate(); resolve(v); };
      const timer = setTimeout(() => done("blocked"), 2000);
      w.onmessage = () => done("allowed");
      w.onerror = () => done("blocked");
    });
    out.worker = await runs(() => new Worker("/__probe-worker.js?probe"));
    out.blobWorker = await runs(() => new Worker(URL.createObjectURL(new Blob(["postMessage(1)"], { type: "text/javascript" }))));
    out.dataWorker = await runs(() => new Worker("data:text/javascript,postMessage(1)"));
    const py = window.__e2e.py;
    out.python = JSON.parse(await py.runPythonAsync(`
import js, json, pyodide.http
r = {}
for key, call in (("js_fetch_same", lambda: js.fetch("/copy.js?pyprobe")),
                  ("js_fetch_other", lambda: js.fetch("https://example.com/pyprobe")),
                  ("pyfetch_same", lambda: pyodide.http.pyfetch("/copy.js?pyprobe2")),
                  ("pyfetch_other", lambda: pyodide.http.pyfetch("https://example.com/pyprobe2"))):
    try:
        await call()
        r[key] = "allowed"
    except Exception:
        r[key] = "blocked"
json.dumps(r)
`));
    return out;
  });
  const flat = { ...probes, ...probes.python };
  delete flat.python;
  check("C9", "after ready: fetch from JS and Python and new workers are blocked",
    Object.values(flat).every((v) => v === "blocked"), JSON.stringify(flat));
  const probeHits = log.filter((l) => l.t > tReady && /probe/.test(l.path));
  check("C9", "no probe reached the server", !probeHits.length, probeHits.map((l) => l.path).join(" "));

  const storage = await page.evaluate(async () => ({
    cookie: document.cookie,
    local: localStorage.length,
    session: sessionStorage.length,
    sw: (await navigator.serviceWorker.getRegistrations()).length,
    idb: (await indexedDB.databases()).length,
  }));
  check("C9", "no cookie, storage or service worker",
    !storage.cookie && !storage.local && !storage.session && !storage.sw && !storage.idb && !(await ctx.cookies()).length, JSON.stringify(storage));

  // every request after ready, before the link-outs: none (the probes were blocked, so they made none)
  const tLinks = Date.now();
  const afterReady = reqs.filter((r) => r.t > tReady && r.t <= tLinks && !r.url.startsWith("blob:"));
  check("C9", "zero requests after ready", !afterReady.length, afterReady.map((r) => r.url).join(" "));
  const serverAfter = log.filter((l) => l.t > tReady);
  check("C9", "server saw nothing after ready", !serverAfter.length, serverAfter.map((l) => l.path).join(" "));

  // link-outs: fixed anchors only, no user data in any URL, intercepted and not followed
  const anchors = await page.$$eval("a[href]", (as) => as.map((a) => a.href));
  const staticHtml = await readFile(path.join(ROOT, "docs", "index.html"), "utf8");
  const staticHrefs = [...staticHtml.matchAll(/<a\s[^>]*href="([^"]+)"/g)].map((m) => new URL(m[1]).href);
  check("C9", "every link is a fixed anchor from index.html", anchors.every((h) => staticHrefs.includes(h)), anchors.join(" "));
  const pageUrl = page.url();
  const clicked = [];
  // new-tab links first: after a same-tab navigation that the 204 cancels, Playwright waits on it
  // and would block the real click a new-tab link needs
  const links = [];
  for (const a of await page.$$("a[href^='http']")) links.push({ a, blank: (await a.getAttribute("target")) === "_blank" });
  links.sort((x, y) => Number(y.blank) - Number(x.blank));
  for (const { a, blank } of links) {
    const href = await a.evaluate((el) => el.href);
    const n = linkOuts.length;
    // a new-tab link gets a real click (a script click has no gesture, so its popup is blocked);
    // a same-tab link gets an in-page click, so Playwright does not wait on the navigation the
    // 204 cancels
    if (blank) {
      await a.scrollIntoViewIfNeeded();
      await a.click();
    } else {
      await a.evaluate((el) => el.click());
    }
    await page.waitForTimeout(800);
    for (const extra of ctx.pages().filter((x) => x !== page)) await extra.close();
    clicked.push({ href, recorded: linkOuts.slice(n).map((l) => l.url), pageStayed: page.url() === pageUrl });
  }
  check("C9", `each of the ${staticHrefs.length} link-outs clicked, intercepted, the page kept`,
    clicked.length === staticHrefs.length && clicked.every((c) => c.recorded.includes(c.href) && c.pageStayed),
    JSON.stringify(clicked));
  const userText = outline.split("\n").map((l) => l.replace(/^[#\-\s|]+/, "").trim()).filter((t) => t.length >= 2);
  const urls = [...reqs.map((r) => r.url), ...linkOuts.map((l) => l.url), ...anchors];
  const leaked = urls.filter((u) => userText.some((t) => decodeURIComponent(u).includes(t)));
  check("C9", "no URL carries outline text", !leaked.length, leaked.join(" "));
  check("C9", "link-outs intercepted, only the fixed anchors", linkOuts.length > 0 && linkOuts.every((l) => staticHrefs.includes(l.url)),
    linkOuts.map((l) => l.url).join(" "));

  await ctx.close();
  server.close();
  // every fill records the face the page passed, for the C10 and C28 replays
  for (const f of fills) Object.assign(f, { ua: agent.tag, cjkFace: agent.face });
  return {
    ua: agent.tag, userAgent: agent.ua, cjkFace: agent.face,
    tReady, tDownloads, tLastDownload, tIdleStart, tIdleEnd, requestsBeforeReady: before.length, fills, outline: "fixtures/reference-outline.md",
    linkOuts, clicked, requests: reqs, serverLog: log, violations,
  };
}

// ------------------------------------------------------------------ C8: error files on the page
const C8 = {
  "legacy.pptx": "legacy_ppt", "encrypted.pptx": "encrypted", "not-powerpoint.pptx": "not_pptx",
  "dangling-relationship.pptx": "bad_file", "zip-bomb.pptx": "too_big", "lying-size.pptx": "bad_file",
  "billion-laughs.pptx": "bad_file", "no-body.pptx": "no_text_layout",
};

async function pageErrors(browser) {
  const { server, port } = await startServer();
  const copy = (await import(path.join(ROOT, "docs", "copy.js"))).COPY;
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`http://127.0.0.1:${port}/`);
  await waitReady(page);
  const files = new Set(await readdir(FIX));
  for (const [file, code] of Object.entries(C8)) {
    if (!files.has(file)) { check("C8", `${file}: fixture exists`, false); continue; }
    await page.setInputFiles("#file", path.join(FIX, file));
    await page.waitForSelector("#template-error:not([hidden])", { timeout: 60000 });
    const text = await page.textContent("#template-error");
    const noDownload = await page.$eval("#plan", (el) => el.hidden);
    const t = Date.now();
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(r)));
    const responsive = Date.now() - t < 500;
    check("C8", `${file}: ${code} message, no download, responsive`, text === copy.templateErrors[code] && noDownload && responsive,
      `${text.slice(0, 40)} | download hidden ${noDownload} | ${Date.now() - t} ms`);
    await page.setInputFiles("#file", []);
  }
  await page.close();
  server.close();
}

// ------------------------------------------------------------------ C13: phone
async function phone(browser) {
  const { server, port } = await startServer();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForTimeout(1200);
  const m = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    steps: [...document.querySelectorAll("#phone-steps li")].filter((li) => li.offsetParent).length,
    copyLink: !!document.getElementById("copy-link").offsetParent,
  }));
  await page.screenshot({ path: path.join(OUT, "c13-phone-390x844.png"), fullPage: true });
  check("C13", "390x844: no horizontal scroll, three steps, copy-link button", m.scroll === 0 && m.steps === 3 && m.copyLink, JSON.stringify(m));
  await page.close();
  server.close();
}

// ------------------------------------------------------------------ what was tested
const sha256 = async (f) => createHash("sha256").update(await readFile(f)).digest("hex");

async function provenance(info) {
  const git = (...a) => execFileSync("git", a, { cwd: ROOT, encoding: "utf8" }).trim();
  const inputs = [path.join(ROOT, info.outline || "fixtures/reference-outline.md"), ...(info.fills || []).map((f) => path.join(FIX, f.template))];
  const out = { commit: git("rev-parse", "HEAD"), dirty: git("status", "--porcelain", "--", "docs", "src", "tests"), inputs: {}, outputs: {} };
  for (const f of inputs) out.inputs[path.relative(ROOT, f)] = await sha256(f);
  for (const f of info.fills || []) out.outputs[path.relative(ROOT, f.file)] = await sha256(f.file);
  return out;
}

// ------------------------------------------------------------------ main
await mkdir(OUT, { recursive: true });
await staticPolicy();
await staticOrigins();
const browser = await chromium.launch({ executablePath: EXE });
const runs = [];
try {
  for (const agent of AGENTS) {
    RUN = agent.tag;
    runs.push(await session(browser, agent));
  }
  RUN = "";
  await pageErrors(browser);
  await phone(browser);
} finally {
  await browser.close();
}
// the fills of both runs in one list, each with its ua and cjkFace (qa/e2e/c10_compare.py replays session.fills)
const info = { outline: "fixtures/reference-outline.md", fills: runs.flatMap((r) => r.fills), runs: runs.map(({ fills, ...r }) => r) };
const failed = checks.filter((c) => !c.ok);
await writeFile(path.join(OUT, "c9-report.json"), JSON.stringify({ tested: await provenance(info), checks, session: info }, null, 1));
for (const c of checks) console.log(c.ok ? "PASS" : "FAIL", c.id, c.name, c.ok ? "" : `-- ${c.detail}`);
console.log(`${checks.length - failed.length} passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
