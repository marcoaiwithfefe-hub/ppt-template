// The page (spec D8). Python runs on the main thread (D1); each step paints its working state
// and yields to the browser before calling Python. At ready the page locks the network (D6).
import { COPY } from "./copy.js";

const PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation";
const MAX_FILE = 100 * 1024 * 1024; // D1b; Python enforces it too
const WHEELS = [
  "python_pptx-1.0.2-py3-none-any.whl",
  "xlsxwriter-3.2.9-py3-none-any.whl",
];
const LOCKDOWN = "connect-src 'none'; img-src data: blob:; worker-src 'none'";
const FONTS = ['400 16px "Noto Serif TC"', '400 16px "Newsreader"', '700 16px "Mentron Serif"'];
const PHONE = window.matchMedia("(max-width: 760px)");

const $ = (id) => document.getElementById(id);
const fmt = (s, vars = {}) => s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
const pick = (path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), COPY);

const state = {
  py: null,
  session: null,
  ready: false,
  loading: false,
  template: null, // { name, layouts, defaults }
  overrides: {},
  plan: null,
  planTimer: 0,
  gen: 0, // bumps on every change to the outline, overrides or template; a plan from an older gen is dropped
};

// ---------------------------------------------------------------- copy into the page
function applyCopy() {
  document.title = COPY.title;
  for (const el of document.querySelectorAll("[data-copy]")) el.textContent = pick(el.dataset.copy);
  for (const el of document.querySelectorAll("[data-copy-placeholder]")) {
    el.placeholder = pick(el.dataset.copyPlaceholder);
  }
  const steps = $("phone-steps");
  for (const line of COPY.phoneSteps) {
    const li = document.createElement("li");
    li.textContent = line;
    steps.append(li);
  }
}

// ---------------------------------------------------------------- status and working state
function setStatus(kind) {
  const el = $("status");
  el.dataset.state = kind;
  $("status-text").textContent = { loading: COPY.loading, ready: COPY.ready, failed: COPY.loadFailed }[kind];
  $("retry").hidden = kind !== "failed";
}

// Show the working state, let the browser paint it, then run the Python step.
async function working(fn) {
  $("working").hidden = false;
  document.body.setAttribute("aria-busy", "true");
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  try {
    return await fn();
  } finally {
    $("working").hidden = true;
    document.body.removeAttribute("aria-busy");
  }
}

// ---------------------------------------------------------------- engine
async function loadEngine() {
  if (state.loading || state.ready) return;
  state.loading = true;
  setStatus("loading");
  try {
    const base = new URL("./", location.href);
    const { loadPyodide } = await import("./vendor/pyodide/pyodide.mjs");
    const vendor = new URL("vendor/pyodide/", base).href;
    // packageBaseUrl set, so Pyodide's default package CDN is never used
    const py = await loadPyodide({ indexURL: vendor, packageBaseUrl: vendor, packages: [] });
    await py.loadPackage([
      "lxml",
      "pillow",
      "typing-extensions",
      ...WHEELS.map((w) => new URL(`vendor/pyodide/${w}`, base).href),
    ]);
    const zip = await (await fetch(new URL("py/deckfill.zip", base))).arrayBuffer();
    py.unpackArchive(zip, "zip", { extractDir: "/home/pyodide/lib" });
    // Import everything now, so nothing loads after the lockdown.
    py.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/lib")
import pptx, pptx.util, lxml.etree, PIL.Image, json, zipfile, re
from deckfill.web import Session
session = Session()
`);
    await Promise.all(FONTS.map((f) => document.fonts.load(f, "中A")));
    await document.fonts.ready;
    state.py = py;
    state.session = py.globals.get("session");
    // The end-to-end test reaches Python through this hook to prove the lockdown covers it (C9).
    if (location.hash === "#e2e") window.__e2e = { py };
    lockdown();
    state.ready = true;
    setStatus("ready");
    enableInputs();
  } catch (err) {
    console.error(err);
    setStatus("failed");
  } finally {
    state.loading = false;
  }
}

function lockdown() {
  const meta = document.createElement("meta");
  meta.httpEquiv = "Content-Security-Policy";
  meta.content = LOCKDOWN;
  document.head.append(meta);
}

function enableInputs() {
  $("file").disabled = false;
  $("drop").classList.remove("is-off");
  $("drop-sub").textContent = COPY.orPick;
  refreshOutlineState();
}

// ---------------------------------------------------------------- step 1
async function loadPromptText() {
  const text = await (await fetch(new URL("prompt.txt", location.href))).text();
  $("prompt-text").textContent = text;
  return text;
}

function bindCopy(button, labelEl, getText, doneEl) {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(getText());
    } catch {
      return;
    }
    if (labelEl) {
      labelEl.textContent = COPY.copied;
      setTimeout(() => (labelEl.textContent = COPY.copyPrompt), 1800);
    }
    if (doneEl) doneEl.hidden = false;
  });
}

// ---------------------------------------------------------------- step 2
function showTemplateError(code) {
  const el = $("template-error");
  el.textContent = COPY.templateErrors[code] || COPY.templateErrors.unknown;
  el.hidden = false;
}

async function readTemplate(file) {
  if (!state.ready || !file) return;
  $("template-error").hidden = true;
  $("downloaded").hidden = true;
  staleNow();
  state.template = null;
  state.overrides = {};
  state.plan = null;
  renderTemplate();
  renderPlan();
  if (file.size > MAX_FILE) {
    showTemplateError("too_big");
    return;
  }
  const result = await working(async () => {
    const bytes = new Uint8Array(await file.arrayBuffer());
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const pyBytes = state.py.toPy(bytes);
    try {
      return JSON.parse(state.session.read(pyBytes, file.name));
    } catch (err) {
      console.error(err);
      return { ok: false, code: "unknown" };
    } finally {
      pyBytes.destroy();
    }
  });
  if (!result.ok) {
    showTemplateError(result.code);
    return;
  }
  state.template = { name: file.name, layouts: result.layouts, masters: result.masters, defaults: result.defaults };
  renderTemplate();
  await replan();
}

function renderTemplate() {
  const t = state.template;
  $("layouts").hidden = !t;
  $("drop").hidden = !!t;
  refreshOutlineState();
  if (!t) return;
  $("template-name").textContent = t.name;
  $("layouts-count").textContent = fmt(COPY.foundLayouts, { n: t.layouts.length });
  const defaults = new Set(Object.values(t.defaults));
  const list = $("layouts-list");
  list.replaceChildren();
  for (let m = 0; m < t.masters; m++) {
    const rows = t.layouts.filter((l) => l.master === m);
    if (!rows.length) continue;
    if (t.masters > 1) {
      const h = document.createElement("p");
      h.className = "master-name";
      h.textContent = fmt(COPY.master, { n: m + 1 });
      list.append(h);
    }
    for (const lay of rows) {
      const row = document.createElement("div");
      row.className = "layout-row";
      const name = document.createElement("span");
      name.className = "layout-row__name";
      name.textContent = lay.name || COPY.unnamed;
      const cls = document.createElement("span");
      cls.className = "layout-row__cls" + (lay.cls === "other" ? " is-other" : "");
      cls.textContent = COPY.classNames[lay.cls] || lay.cls;
      const def = document.createElement("span");
      def.className = "layout-row__default";
      def.textContent = defaults.has(lay.id) ? COPY.defaultMark : "";
      row.append(name, cls, def);
      list.append(row);
    }
  }
}

// ---------------------------------------------------------------- step 3
function refreshOutlineState() {
  $("need-template").hidden = !!state.template;
}

// The current plan no longer matches what the user sees: block the download at once (F1).
function staleNow() {
  state.gen += 1;
  $("download").disabled = true;
  $("downloaded").hidden = true;
}

function schedulePlan() {
  staleNow();
  clearTimeout(state.planTimer);
  state.planTimer = setTimeout(replan, 450);
}

async function replan() {
  clearTimeout(state.planTimer);
  $("outline-error").hidden = true;
  $("downloaded").hidden = true;
  const gen = state.gen;
  const text = $("outline").value;
  if (!state.template || !text.trim()) {
    state.plan = null;
    renderPlan();
    return;
  }
  const result = await working(async () => {
    try {
      return JSON.parse(state.session.plan(text, JSON.stringify(state.overrides)));
    } catch (err) {
      console.error(err);
      return { ok: false, code: "unknown" };
    }
  });
  if (gen !== state.gen) return; // the outline or a layout changed while this plan was made
  if (!result.ok) {
    state.plan = null;
    renderPlan();
    const el = $("outline-error");
    el.textContent = COPY.outlineErrors[result.code] || COPY.outlineErrors.unknown;
    el.hidden = false;
    return;
  }
  state.plan = result;
  renderPlan();
}

function layoutName(id) {
  const lay = state.template.layouts.find((l) => l.id === id);
  if (!lay) return id;
  const name = lay.name || COPY.unnamed;
  return state.template.masters > 1 ? `${name}（${fmt(COPY.master, { n: lay.master + 1 })}）` : name;
}

function renderPlan() {
  const p = state.plan;
  $("plan").hidden = !p;
  if (!p) return;
  $("slides-heading").textContent = fmt(COPY.slidesHeading, { n: p.slides.length });
  const body = $("slides");
  body.replaceChildren();
  p.slides.forEach((s, i) => {
    const tr = document.createElement("tr");
    if (s.part > 0) tr.className = "cont";
    const no = document.createElement("td");
    no.className = "no";
    no.textContent = fmt(COPY.slideNo, { n: i + 1 });
    const title = document.createElement("td");
    title.className = "title";
    title.textContent = s.title;
    const lay = document.createElement("td");
    lay.className = "lay";
    if (s.part === 0) {
      const src = p.sources[s.source];
      const sel = document.createElement("select");
      sel.setAttribute("aria-label", `${COPY.layoutLabel}：${s.title}`);
      for (const id of src.compatible) {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = layoutName(id);
        opt.selected = id === src.chosen;
        sel.append(opt);
      }
      sel.disabled = src.compatible.length < 2;
      sel.addEventListener("change", () => {
        state.overrides[s.source] = sel.value;
        staleNow();
        replan();
      });
      lay.append(sel);
    } else {
      const f = document.createElement("span");
      f.className = "lay__follows";
      f.textContent = layoutName(s.layout);
      lay.append(f);
    }
    const fit = document.createElement("td");
    fit.className = "fit" + (s.fit === "fits" ? "" : " is-flag");
    fit.textContent = COPY.fit[s.fit] || s.fit;
    tr.append(no, title, lay, fit);
    body.append(tr);
  });
  const list = $("warnings-list");
  list.replaceChildren();
  for (const w of p.warnings) {
    const li = document.createElement("li");
    const tpl = COPY.warnings[w.code];
    li.textContent = tpl ? fmt(tpl, { line: w.line, text: w.text }) : `${w.line} ${w.text}`;
    list.append(li);
  }
  $("warnings").hidden = !p.warnings.length;
  $("download-label").textContent = fmt(COPY.download, { name: p.name });
  $("download").disabled = false;
}

async function download() {
  if (!state.plan || !state.template) return;
  // Read the outline and layouts now; Python plans from exactly these and fills in one call (F1).
  const text = $("outline").value;
  const overrides = JSON.stringify(state.overrides);
  const result = await working(async () => {
    let out;
    try {
      out = state.session.fill(text, overrides);
      return { bytes: out.toJs(), name: state.session.fill_name };
    } catch (err) {
      console.error(err);
      return null;
    } finally {
      if (out) out.destroy();
    }
  });
  if (!result) {
    const el = $("outline-error");
    el.textContent = COPY.outlineErrors.unknown;
    el.hidden = false;
    return;
  }
  const { bytes, name } = result;
  const url = URL.createObjectURL(new Blob([bytes], { type: PPTX_TYPE }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.pptx`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  $("downloaded").hidden = false;
}

function reset() {
  staleNow();
  state.template = null;
  state.overrides = {};
  state.plan = null;
  $("outline").value = "";
  $("file").value = "";
  $("template-error").hidden = true;
  $("outline-error").hidden = true;
  $("downloaded").hidden = true;
  renderTemplate();
  renderPlan();
  window.scrollTo({ top: $("step2").offsetTop - 24 });
}

// ---------------------------------------------------------------- wiring
function wire() {
  const drop = $("drop");
  drop.classList.add("is-off");
  $("file").addEventListener("change", (e) => readTemplate(e.target.files[0]));
  for (const ev of ["dragenter", "dragover"]) {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      if (state.ready) drop.classList.add("is-over");
    });
  }
  for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, () => drop.classList.remove("is-over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    readTemplate(e.dataTransfer.files[0]);
  });
  // a file dropped outside the box must not navigate the tab to it
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());

  $("change-template").addEventListener("click", () => {
    staleNow();
    state.template = null;
    state.overrides = {};
    state.plan = null;
    $("file").value = "";
    renderTemplate();
    renderPlan();
    $("file").click();
  });
  $("outline").addEventListener("input", schedulePlan);
  $("download").addEventListener("click", download);
  $("reset").addEventListener("click", reset);
  $("retry").addEventListener("click", () => {
    loadPromptText().catch(() => {});
    loadEngine();
  });

  let promptText = "";
  bindCopy($("copy-prompt"), $("copy-prompt-label"), () => promptText);
  bindCopy($("copy-link"), null, () => location.href, $("copy-link-done"));
  return (text) => (promptText = text);
}

function start() {
  applyCopy();
  const setPrompt = wire();
  if (PHONE.matches) {
    // The phone view explains and hands over the link; the engine loads if the window widens.
    PHONE.addEventListener("change", () => !PHONE.matches && boot(setPrompt), { once: true });
    return;
  }
  boot(setPrompt);
}

function boot(setPrompt) {
  setStatus("loading");
  loadPromptText()
    .then(setPrompt)
    .catch(() => {})
    .finally(loadEngine);
}

start();
