// Fill time on the page (QA round 1 handoff, item 5): the reel's cover says 3秒, so this prints the time from the
// click on download to the download event, on Bullen and on Marco's template, filled with the reference outline on
// the route the page picks. Three runs each. Cold: the first fill in a fresh browser context (empty cache) after the
// page is ready and the template is read. Warm: a second click on the same page straight after. The template read
// (file chosen to step 2 shown) is printed beside it. No network throttle: after ready the page makes no request.
// Run: node tests/e2e/fill_time.mjs   (writes qa/e2e/fill-time.json)
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(ROOT, "qa", "e2e");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const TEMPLATES = ["bullen-free-presentation-template.pptx", "marco-year-in-breakdowns.pptx"];
const RUNS = 3;
const outline = await readFile(path.join(ROOT, "fixtures", "reference-outline.md"), "utf8");
const ms = (t0) => Math.round(Number(process.hrtime.bigint() - t0) / 1e6);

async function clickToDownload(page) {
  const t0 = process.hrtime.bigint();
  const [d] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), page.click("#download")]);
  await d.path(); // the bytes are written
  return { ms: ms(t0), name: d.suggestedFilename() };
}

await mkdir(OUT, { recursive: true });
const { server, port } = await startServer();
const browser = await chromium.launch({ executablePath: EXE });
const results = [];
try {
  for (const name of TEMPLATES) {
    for (let run = 1; run <= RUNS; run++) {
      const context = await browser.newContext({ acceptDownloads: true });
      const page = await context.newPage();
      await page.goto(`http://127.0.0.1:${port}/`);
      await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 120000 });
      const tRead = process.hrtime.bigint();
      await page.setInputFiles("#file", path.join(ROOT, "qa", "real-templates", name));
      await page.waitForSelector("#layouts:not([hidden])", { timeout: 120000 });
      const readMs = ms(tRead);
      await page.fill("#outline", outline);
      await page.waitForFunction(() => !document.getElementById("download").disabled, null, { timeout: 120000 });
      const route = await page.evaluate(() => (document.getElementById("route-sample")?.getAttribute("aria-pressed") === "true" ? "sample" : "layout"));
      const cold = await clickToDownload(page);
      await page.waitForFunction(() => !document.getElementById("download").disabled, null, { timeout: 120000 });
      const warm = await clickToDownload(page);
      results.push({ template: name, run, route, read_ms: readMs, cold_ms: cold.ms, warm_ms: warm.ms, download: cold.name });
      console.log(name, `run ${run}`, route, `read ${readMs} ms`, `fill cold ${cold.ms} ms`, `fill warm ${warm.ms} ms`);
      await context.close();
    }
  }
} finally {
  await browser.close();
  server.close();
}
const commit = execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
const dirty = execFileSync("git", ["status", "--porcelain", "--", "src", "docs"], { cwd: ROOT, encoding: "utf8" }).trim() !== "";
const summary = {};
for (const name of TEMPLATES) {
  const rs = results.filter((r) => r.template === name);
  const pick = (k) => rs.map((r) => r[k]);
  summary[name] = { read_ms: pick("read_ms"), cold_ms: pick("cold_ms"), warm_ms: pick("warm_ms"),
    cold_max_ms: Math.max(...pick("cold_ms")), warm_max_ms: Math.max(...pick("warm_ms")) };
}
await writeFile(path.join(OUT, "fill-time.json"), JSON.stringify({ commit, dirty_src_or_docs: dirty, machine: process.platform + " " + process.arch,
  browser: "chromium headless shell (playwright-core 1.64.1)", results, summary }, null, 1));
console.log(JSON.stringify(summary));
