// Layout-override fix on the page: a layout picked for one slide follows that slide when the
// outline gains or loses a slide above it, and an override whose slide is gone is dropped with a
// one-line note instead of landing on whatever slide now sits at its old position.
// Run: node tests/e2e/override_follow.mjs   (exit 1 on failure)
import { chromium } from "playwright-core";
import { spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { COPY } from "../../docs/copy.js";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = path.join(ROOT, "qa", "e2e");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const THREE = "# 封面\n\n## 甲\n- 一\n\n## 乙\n- 二\n";
const INSERTED = "# 封面\n\n## 新\n- 新\n\n## 甲\n- 一\n\n## 乙\n- 二\n";
const DELETED = "# 封面\n\n## 新\n- 新\n\n## 甲\n- 一\n";

// title and layout name of every slide in the deck, through the reader the CPython tests use
function deckLayouts(file) {
  const r = spawnSync(path.join(ROOT, ".venv", "bin", "python"), ["-c", `
import sys; sys.path[:0] = ["${ROOT}/tests", "${ROOT}/src"]
from oracle import read_deck
for s in read_deck(open(sys.argv[1], "rb").read()):
    print(f"{s.title}\\t{s.layout_name}")
`, file], { encoding: "utf8" });
  return Object.fromEntries(r.stdout.trim().split("\n").map((l) => l.split("\t")));
}

const checks = [];
const check = (name, ok, detail = "") => checks.push({ name, ok: !!ok, detail });

const waitForPlan = (page, selects) =>
  page.waitForFunction(
    (n) => !document.getElementById("download").disabled && document.querySelectorAll("#slides select").length === n,
    selects,
    { timeout: 60000 },
  );
// title -> [value, option text] for every slide row with a layout picker
const pickers = (page) =>
  page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll("#slides tr")]
        .filter((tr) => tr.querySelector("select"))
        .map((tr) => {
          const sel = tr.querySelector("select");
          return [tr.querySelector("td.title").textContent, [sel.value, sel.selectedOptions[0].textContent]];
        }),
    ),
  );
const notes = (page) =>
  page.evaluate(() => (document.getElementById("warnings").hidden ? [] : [...document.querySelectorAll("#warnings-list li")].map((li) => li.textContent)));

await mkdir(OUT, { recursive: true });
const { server, port } = await startServer();
const browser = await chromium.launch({ executablePath: EXE });
try {
  const page = await (await browser.newContext({ acceptDownloads: true })).newPage();
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 120000 });
  await page.setInputFiles("#file", path.join(ROOT, "fixtures", "out", "typed.pptx"));
  await page.waitForSelector("#layouts:not([hidden])");
  await page.fill("#outline", THREE);
  await waitForPlan(page, 3);
  const start = await pickers(page);
  const [jiaDefault, jiaDefaultName] = start["甲"];

  // pick a layout other than the default for 乙
  const yi = page.locator("#slides tr", { has: page.locator("td.title", { hasText: /^乙$/ }) }).locator("select");
  const [other, otherName] = await yi.evaluate((sel) => {
    const o = [...sel.options].find((x) => x.value !== sel.value);
    return [o.value, o.textContent];
  });
  await yi.selectOption(other);
  await waitForPlan(page, 3);
  check("the pick is shown on 乙", (await pickers(page))["乙"][0] === other);

  // 1: a slide inserted above both
  await page.fill("#outline", INSERTED);
  await waitForPlan(page, 4);
  const after = await pickers(page);
  check("after an insert above, 乙 keeps its layout", after["乙"][0] === other, JSON.stringify(after));
  check("after an insert above, 甲 (now at 乙's old place) keeps its default", after["甲"][0] === jiaDefault, JSON.stringify(after));
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), page.click("#download")]);
  const file = path.join(OUT, "override-follow.pptx");
  await dl.saveAs(file);
  const deck = deckLayouts(file);
  check("the download puts 乙 on the picked layout", deck["乙"] === otherName, JSON.stringify(deck));
  check("the download keeps 甲 on its default", deck["甲"] === jiaDefaultName, JSON.stringify(deck));

  // 2: the overridden slide deleted
  await page.fill("#outline", DELETED);
  await waitForPlan(page, 3);
  const gone = await pickers(page);
  const note = COPY.warnings.layout_gone ? COPY.warnings.layout_gone.replace("{text}", "乙") : null;
  check("after 乙 is deleted, no slide takes its layout", Object.values(gone).every(([v]) => v !== other), JSON.stringify(gone));
  check("after 乙 is deleted, 甲 keeps its default", gone["甲"][0] === jiaDefault, JSON.stringify(gone));
  const shown = await notes(page);
  check("a one-line note says the layout for 乙 was dropped", note && shown.includes(note), JSON.stringify(shown));

  // 3: the next edit: the note has done its job and the override is forgotten
  await page.fill("#outline", DELETED + "- 二\n");
  await waitForPlan(page, 3);
  const later = await notes(page);
  check("the note goes with the next edit", note && !later.includes(note), JSON.stringify(later));
  check("甲 still keeps its default", (await pickers(page))["甲"][0] === jiaDefault);
} finally {
  await browser.close();
  server.close();
}
for (const c of checks) console.log(c.ok ? "PASS" : "FAIL", "override", c.name, c.ok ? "" : `-- ${c.detail}`);
const failed = checks.filter((c) => !c.ok).length;
console.log(`${checks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
