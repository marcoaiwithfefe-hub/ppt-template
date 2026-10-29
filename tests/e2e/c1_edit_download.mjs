// C1 on the page (Codex round 1 F1): an edit followed at once by a download must ship the new
// text. Download is disabled the moment the outline changes, and the fill plans from the outline
// and overrides read at the click, so even a click that lands mid-edit cannot ship an old plan.
// Run: node tests/e2e/c1_edit_download.mjs   (exit 1 on failure)
import { chromium } from "playwright-core";
import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(ROOT, "qa", "e2e");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const outline = (title) => `# ${title}\n副題\n\n## 三個目標\n- 第一點\n- 第二點\n`;

// every text run in the deck's slides, through the same reader the CPython tests use
function deckText(file) {
  const r = spawnSync(path.join(ROOT, ".venv", "bin", "python"), ["-c", `
import sys; sys.path[:0] = ["${ROOT}/tests", "${ROOT}/src"]
from oracle import read_deck
for s in read_deck(open(sys.argv[1], "rb").read()):
    print(s.title)
    for col in s.bodies:
        for _, t in col: print(t)
`, file], { encoding: "utf8" });
  return r.stdout;
}

const checks = [];
const check = (name, ok, detail = "") => checks.push({ name, ok: !!ok, detail });

await mkdir(OUT, { recursive: true });
const { server, port } = await startServer();
const browser = await chromium.launch({ executablePath: EXE });
try {
  const page = await (await browser.newContext({ acceptDownloads: true })).newPage();
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 120000 });
  await page.setInputFiles("#file", path.join(ROOT, "fixtures", "out", "wui-tung.pptx"));
  await page.waitForSelector("#layouts:not([hidden])");
  await page.fill("#outline", outline("OLD 舊標題"));
  await page.waitForSelector("#plan:not([hidden])");
  await page.waitForFunction(() => !document.getElementById("download").disabled);

  // 1: a script click straight after the edit, which skips Playwright's wait for an enabled button
  await page.fill("#outline", outline("NEW1 新標題"));
  const disabledAtOnce = await page.evaluate(() => document.getElementById("download").disabled);
  check("download is disabled as soon as the outline changes", disabledAtOnce);
  const [d1] = await Promise.all([
    page.waitForEvent("download", { timeout: 60000 }),
    page.evaluate(() => {
      const b = document.getElementById("download");
      b.disabled = false; // force the click through, as a stale UI state would allow
      b.click();
    }),
  ]);
  const f1 = path.join(OUT, "c1-edit-download-1.pptx");
  await d1.saveAs(f1);
  const t1 = deckText(f1);
  check("forced click mid-edit ships the new outline", t1.includes("NEW1 新標題") && !t1.includes("OLD"), t1.split("\n")[0]);

  // 2: an ordinary click straight after the next edit
  await page.fill("#outline", outline("NEW2 新標題"));
  const [d2] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.click("#download")]);
  const f2 = path.join(OUT, "c1-edit-download-2.pptx");
  await d2.saveAs(f2);
  const t2 = deckText(f2);
  check("ordinary click after an edit ships the new outline", t2.includes("NEW2 新標題") && !t2.includes("NEW1"), t2.split("\n")[0]);
  check("download name follows the new title", d2.suggestedFilename() === "NEW2 新標題.pptx", d2.suggestedFilename());
} finally {
  await browser.close();
  server.close();
}
for (const c of checks) console.log(c.ok ? "PASS" : "FAIL", "C1 page", c.name, c.ok ? "" : `-- ${c.detail}`);
const failed = checks.filter((c) => !c.ok).length;
console.log(`${checks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
