// C12 load and responsiveness, in headless Chromium on the local static server.
// Cold load (empty cache) and warm reload at 20 Mbps down, 40 ms latency; Long Tasks across read,
// plan and fill for every G0 template and fixture and for the D1b worst case; a screenshot taken
// during the longest task; click response after each step. Numbers in qa/e2e/c12-report.json.
// SCRATCH=hkust14 adds Fable's one-off: read hkust-template14 (73.7 MB) with the file cap raised
// in Python for that run only (the shipped cap stays 50 MB).
// Run: node tests/e2e/c12_load.mjs   (needs .venv/bin/python qa/c12/make_worst.py first)
import { chromium } from "playwright-core";
import { readFile, writeFile, readdir, stat } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(ROOT, "qa", "e2e");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const NET = { offline: false, latency: 40, downloadThroughput: (20e6 / 8), uploadThroughput: (20e6 / 8) };
const BARS = { coldS: 15, coldMB: 25, warmS: 5, taskS: 3, worstTaskS: 10, clickMs: 500 };
const FILLABLE = [
  "typed.pptx", "custom.pptx", "contradict.pptx", "two-masters.pptx", "no-two.pptx", "no-section.pptx",
  "no-title.pptx", "only-content.pptx", "small-body.pptx", "small-body-insets.pptx", "nowrap.pptx",
  "footer-active.pptx", "footer-mixed.pptx", "footer-two-masters.pptx", "footer-fixed-date.pptx",
  "footer-hf.pptx", "external-link.pptx", "sections.pptx", "wui-tung.pptx", "wui-tung.potx", "rels-order.pptx",
];
const REFUSED = ["legacy.pptx", "encrypted.pptx", "not-powerpoint.pptx", "dangling-relationship.pptx",
  "zip-bomb.pptx", "lying-size.pptx", "billion-laughs.pptx", "no-body.pptx", "missing-embed.pptx", "missing-target.pptx"];

const INIT = () => {
  window.__lt = [];
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); })
    .observe({ type: "longtask", buffered: true });
};

const report = { bars: BARS, net: "20 Mbps down, 40 ms latency", checks: [] };
const check = (name, ok, detail) => report.checks.push({ name, ok: !!ok, detail });

async function waitReady(page) {
  await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 180000 });
}

async function idle(page) {
  await page.waitForFunction(() => document.getElementById("working").hidden, null, { timeout: 180000 });
}

// longest long task (ms) that started after `since` (page clock)
const longest = (page, since) => page.evaluate((s) => Math.max(0, ...window.__lt.filter(([t]) => t >= s).map(([, d]) => d)), since);
const now = (page) => page.evaluate(() => performance.now());

async function clickResponse(page) {
  const t = Date.now();
  await page.click("#step1 details:nth-of-type(1) summary");
  await page.waitForFunction(() => document.querySelector("#step1 details").open, null, { timeout: 5000 });
  const ms = Date.now() - t;
  await page.click("#step1 details:nth-of-type(1) summary");
  return ms;
}

// one template through read, plan and fill; returns the longest task per step and click times
async function runOne(page, file, outline, shot) {
  const r = { file: path.basename(file) };
  let t = await now(page);
  await page.setInputFiles("#file", file);
  await page.waitForFunction(() => !document.getElementById("layouts").hidden || !document.getElementById("template-error").hidden, null, { timeout: 180000 });
  await idle(page);
  r.readMs = await longest(page, t);
  r.clickAfterReadMs = await clickResponse(page);
  r.refused = await page.$eval("#template-error", (e) => (e.hidden ? null : e.textContent.slice(0, 30)));
  if (r.refused) return r;
  t = await now(page);
  await page.fill("#outline", outline);
  await page.waitForFunction(() => !document.getElementById("plan").hidden || !document.getElementById("outline-error").hidden, null, { timeout: 180000 });
  await idle(page);
  r.planMs = await longest(page, t);
  r.clickAfterPlanMs = await clickResponse(page);
  t = await now(page);
  const dl = page.waitForEvent("download", { timeout: 300000 });
  const clicked = page.click("#download");
  let cast = null;
  if (shot) {
    // The screen during a main-thread task is the last frame painted before it. Screencast frames
    // carry their paint time, so the frame shown during the longest task can be picked after it.
    cast = { cdp: await page.context().newCDPSession(page), frames: [] };
    cast.cdp.on("Page.screencastFrame", (f) => {
      cast.frames.push({ ts: f.metadata.timestamp * 1000, data: f.data });
      cast.cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
    });
    await cast.cdp.send("Page.startScreencast", { format: "png", everyNthFrame: 1 });
  }
  await clicked;
  await (await dl).path();
  await idle(page);
  r.fillMs = await longest(page, t);
  if (cast) {
    await cast.cdp.send("Page.stopScreencast");
    const [start, dur] = await page.evaluate((s) => {
      const tasks = window.__lt.filter(([t0]) => t0 >= s).sort((a, b) => b[1] - a[1]);
      return [performance.timeOrigin + tasks[0][0], tasks[0][1]];
    }, t);
    const before = cast.frames.filter((f) => f.ts <= start + 5).sort((a, b) => b.ts - a.ts)[0];
    const file = path.join(OUT, "c12-working-during-longest-task.png");
    if (before) await writeFile(file, Buffer.from(before.data, "base64"));
    const probe = before && spawnSync(path.join(ROOT, ".venv", "bin", "python"), ["-c",
      "import sys;from PIL import Image;im=Image.open(sys.argv[1]).convert('RGB');w,h=im.size;print(min(im.getpixel((w//2,h-50))))", file]);
    r.shot = { frames: cast.frames.length, taskMs: Math.round(dur), frameBeforeTaskMs: before ? Math.round(start - before.ts) : null,
      overlayPixel: probe ? Number(String(probe.stdout).trim()) : null };
    r.shotWhileWorking = !!before && r.shot.overlayPixel >= 240;
  }
  r.clickAfterFillMs = await clickResponse(page);
  await page.click("#reset");
  return r;
}

async function main() {
  const { server, port } = await startServer();
  const url = `http://127.0.0.1:${port}/#e2e`;
  const browser = await chromium.launch({ executablePath: EXE });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", NET);
  let bytes = 0;
  cdp.on("Network.loadingFinished", (e) => (bytes += e.encodedDataLength));

  // cold: fresh context, empty cache
  let t = Date.now();
  await page.goto(url);
  await waitReady(page);
  report.coldReadyS = (Date.now() - t) / 1000;
  report.coldTransferMB = bytes / 1e6;
  check(`cold ready ${report.coldReadyS.toFixed(1)} s (bar ${BARS.coldS})`, report.coldReadyS <= BARS.coldS);
  check(`cold transfer ${report.coldTransferMB.toFixed(1)} MB (bar ${BARS.coldMB})`, report.coldTransferMB <= BARS.coldMB);

  // warm: a second visit in the same context (a navigation, not a reload: reload revalidates
  // every file, which a returning visitor does not do)
  bytes = 0;
  await page.goto("about:blank");
  t = Date.now();
  await page.goto(url);
  await waitReady(page);
  report.warmReadyS = (Date.now() - t) / 1000;
  report.warmTransferMB = bytes / 1e6;
  check(`warm ready ${report.warmReadyS.toFixed(1)} s, ${report.warmTransferMB.toFixed(2)} MB transferred (bar ${BARS.warmS} s)`, report.warmReadyS <= BARS.warmS);
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });

  const outline = await readFile(path.join(ROOT, "fixtures", "reference-outline.md"), "utf8");
  const real = (await readdir(path.join(ROOT, "qa", "real-templates"))).filter((f) => /\.(pptx|potx)$/.test(f));
  const files = [
    ...real.map((f) => path.join(ROOT, "qa", "real-templates", f)),
    ...[...FILLABLE, ...REFUSED].map((f) => path.join(ROOT, "fixtures", "out", f)),
  ];
  report.runs = [];
  for (const f of files) report.runs.push(await runOne(page, f, outline, false));
  const ordinary = report.runs.flatMap((r) => [r.readMs, r.planMs, r.fillMs].filter((x) => x != null));
  const clicks = report.runs.flatMap((r) => [r.clickAfterReadMs, r.clickAfterPlanMs, r.clickAfterFillMs].filter((x) => x != null));
  const worstOrd = report.runs.reduce((a, r) => Math.max(a, r.readMs || 0, r.planMs || 0, r.fillMs || 0), 0);
  const worstRun = report.runs.find((r) => [r.readMs, r.planMs, r.fillMs].includes(worstOrd));
  check(`longest task on G0 templates and fixtures ${(worstOrd / 1000).toFixed(2)} s, ${worstRun?.file} (bar ${BARS.taskS})`, Math.max(...ordinary) <= BARS.taskS * 1000);
  check(`slowest click response after a step ${Math.max(...clicks)} ms (bar ${BARS.clickMs})`, Math.max(...clicks) <= BARS.clickMs);

  // worst case the D1b caps allow
  const worstFile = path.join(ROOT, "qa", "c12", "worst-case.pptx");
  const worstOutline = await readFile(path.join(ROOT, "qa", "c12", "worst-outline.md"), "utf8");
  report.worst = { fileMB: (await stat(worstFile)).size / 1e6, ...(await runOne(page, worstFile, worstOutline, true)) };
  report.worst.wasmHeapMB = await page.evaluate(() => window.__e2e.py._module.HEAPU8.byteLength / 1e6);
  const w = report.worst;
  const wMax = Math.max(w.readMs || 0, w.planMs || 0, w.fillMs || 0);
  check(`worst case longest task ${(wMax / 1000).toFixed(2)} s (bar ${BARS.worstTaskS}); read ${w.readMs} plan ${w.planMs} fill ${w.fillMs} ms`, !w.refused && wMax <= BARS.worstTaskS * 1000, w.refused || "");
  check(`worst case click response ${Math.max(w.clickAfterReadMs, w.clickAfterPlanMs || 0, w.clickAfterFillMs || 0)} ms (bar ${BARS.clickMs})`,
    Math.max(w.clickAfterReadMs, w.clickAfterPlanMs || 0, w.clickAfterFillMs || 0) <= BARS.clickMs);
  check(`working state on screen during the longest task (qa/e2e/c12-working-during-longest-task.png)`, w.shotWhileWorking === true, JSON.stringify(w.shot));

  if (process.env.SCRATCH === "hkust14") {
    // Fable's one-off: the 73.7 MB HKUST template with the file cap raised in Python, this run only,
    // on a fresh page so its memory is its own
    const sctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await sctx.addInitScript(INIT);
    const page = await sctx.newPage();
    await page.goto(url);
    await waitReady(page);
    const f = path.join(ROOT, "qa", "real-templates", "hkust-template14.potx");
    await page.setInputFiles("#file", f); // the page refuses it (too_big); the file stays on the input
    await idle(page);
    const heapBefore = await page.evaluate(() => window.__e2e.py._module.HEAPU8.byteLength / 1e6);
    const t0 = await now(page);
    const res = await page.evaluate(async () => {
      const file = document.getElementById("file").files[0];
      const bytes = new Uint8Array(await file.arrayBuffer());
      const py = window.__e2e.py;
      py.runPython("import deckfill.package as P; P.MAX_FILE = 100 * 1024 * 1024; P.MAX_TOTAL = 600 * 1024 * 1024");
      const pb = py.toPy(bytes);
      const t = performance.now();
      const out = py.globals.get("session").read(pb, file.name);
      const ms = performance.now() - t;
      pb.destroy();
      py.runPython("import deckfill.package as P; P.MAX_FILE = 50 * 1024 * 1024; P.MAX_TOTAL = 300 * 1024 * 1024");
      return { ms, out: out.slice(0, 120) };
    });
    report.scratchHkust14 = {
      note: "scratch run only: Python caps raised for this read, shipped cap is 50 MB",
      readCallMs: Math.round(res.ms), longestTaskMs: await longest(page, t0), result: res.out,
      wasmHeapBeforeMB: heapBefore, wasmHeapAfterMB: await page.evaluate(() => window.__e2e.py._module.HEAPU8.byteLength / 1e6),
    };
    await sctx.close();
  }

  await browser.close();
  server.close();
  await writeFile(path.join(OUT, "c12-report.json"), JSON.stringify(report, null, 1));
  for (const c of report.checks) console.log(c.ok ? "PASS" : "FAIL", "C12", c.name, c.detail ? `-- ${c.detail}` : "");
  if (report.scratchHkust14) console.log("SCRATCH hkust14", JSON.stringify(report.scratchHkust14));
  const failed = report.checks.filter((c) => !c.ok).length;
  console.log(`${report.checks.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}

await main();
