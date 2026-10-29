// Codex round 1 F9: a prompt that fails to load must show, not leave a ready page copying nothing.
// The first load of prompt.txt answers 500; the page must show the retry state with Copy disabled
// and must not go ready. After retry the prompt loads, the page goes ready and Copy puts the
// prompt on the clipboard. Run: node tests/e2e/f9_prompt_load.mjs   (exit 1 on failure)
import { chromium } from "playwright-core";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const checks = [];
const check = (name, ok, detail = "") => checks.push({ name, ok: !!ok, detail });

const { server, port } = await startServer();
const origin = `http://127.0.0.1:${port}`;
const browser = await chromium.launch({ executablePath: EXE });
try {
  const ctx = await browser.newContext();
  await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
  let fail = true;
  await ctx.route("**/prompt.txt", (route) => (fail ? route.fulfill({ status: 500, body: "" }) : route.continue()));
  const page = await ctx.newPage();
  await page.goto(`${origin}/`);
  await page.waitForFunction(() => ["ready", "failed"].includes(document.getElementById("status").dataset.state), null, { timeout: 120000 });
  await page.waitForTimeout(1500); // a ready that arrives late would show here
  const first = await page.evaluate(() => ({
    state: document.getElementById("status").dataset.state,
    retry: !document.getElementById("retry").hidden,
    copyDisabled: document.getElementById("copy-prompt").disabled,
  }));
  check("prompt failure shows the retry state, not ready", first.state === "failed" && first.retry, JSON.stringify(first));
  check("Copy is disabled while the prompt is missing", first.copyDisabled, JSON.stringify(first));

  fail = false;
  if (!first.retry) throw new Error("no retry button to press");
  await page.click("#retry");
  await page.waitForFunction(() => document.getElementById("status").dataset.state === "ready", null, { timeout: 120000 });
  const enabled = await page.evaluate(() => !document.getElementById("copy-prompt").disabled);
  check("after retry the page is ready and Copy is enabled", enabled);
  await page.click("#copy-prompt");
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  const prompt = await readFile(path.join(ROOT, "docs", "prompt.txt"), "utf8");
  check("Copy puts the prompt on the clipboard after retry", clip === prompt, `${clip.length} vs ${prompt.length} chars`);
} catch (err) {
  check("the flow ran to the end", false, err.message.split("\n")[0]);
} finally {
  await browser.close();
  server.close();
}
for (const c of checks) console.log(c.ok ? "PASS" : "FAIL", "F9", c.name, c.ok ? "" : `-- ${c.detail}`);
const failed = checks.filter((c) => !c.ok).length;
console.log(`${checks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
