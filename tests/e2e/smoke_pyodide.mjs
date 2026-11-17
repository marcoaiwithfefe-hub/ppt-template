// Smoke: Pyodide from docs/vendor loads deckfill and fills the reference outline.
import { chromium } from "playwright-core";
import { readFile, writeFile } from "node:fs/promises";
import { startServer } from "./server.mjs";

const EXE = process.env.CHROME || `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const { server, port } = await startServer();
const browser = await chromium.launch({ executablePath: EXE });
const page = await browser.newPage();
page.on("console", (m) => console.log("console:", m.text()));
await page.goto(`http://127.0.0.1:${port}/__blank`);
const tpl = [...await readFile("fixtures/out/wui-tung.pptx")];
const outline = await readFile("fixtures/reference-outline.md", "utf8");
const t0 = Date.now();
const res = await page.evaluate(async ({ tpl, outline }) => {
  const { loadPyodide } = await import("/vendor/pyodide/pyodide.mjs");
  const t = performance.now();
  const py = await loadPyodide({ indexURL: "/vendor/pyodide/", packages: [] });
  await py.loadPackage(["lxml", "pillow", "typing-extensions",
    "/vendor/pyodide/python_pptx-1.0.2-py3-none-any.whl", "/vendor/pyodide/xlsxwriter-3.2.9-py3-none-any.whl"]);
  const zip = await (await fetch("/py/deckfill.zip")).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/home/pyodide/lib" });
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
  const ready = performance.now() - t;
  py.globals.set("tpl", py.toPy(new Uint8Array(tpl)));
  py.globals.set("outline", outline);
  const t2 = performance.now();
  const out = py.runPython(`
from deckfill import read_template, parse_outline, plan_deck, fill
data = bytes(tpl)
info = read_template(data, "wui-tung.pptx")
plan = plan_deck(info, parse_outline(outline))
fill(data, "wui-tung.pptx", plan)
`);
  return { ready, fill: performance.now() - t2, bytes: [...out.toJs()] };
}, { tpl, outline });
await writeFile(process.argv[2] || "/dev/null", Buffer.from(res.bytes));
console.log(JSON.stringify({ readyMs: Math.round(res.ready), fillMs: Math.round(res.fill), outBytes: res.bytes.length, wallMs: Date.now() - t0 }));
await browser.close(); server.close();
