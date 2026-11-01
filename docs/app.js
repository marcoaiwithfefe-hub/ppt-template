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
  template: null, // { name, layouts, defaults, routes, samples }
  route: "", // rev 8: "sample" or "layout" (D11); the template's default until the user switches
  overrides: [], // { title, kind, nth, count, layout[, route] } per pick; the bridge places each on its slide
  plan: null,
  planTimer: 0,
  gen: 0, // bumps on every change to the outline, overrides or template; a plan from an older gen is dropped
  promptText: "",
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
// The prompt loads before the engine, so before the lockdown; Copy stays off until it is in (F9).
async function loadPromptText() {
  const res = await fetch(new URL("prompt.txt", location.href));
  if (!res.ok) throw new Error(`prompt.txt: HTTP ${res.status}`);
  const text = await res.text();
  if (!text.trim()) throw new Error("prompt.txt is empty");
  state.promptText = text;
  $("prompt-text").textContent = text;
  $("copy-prompt").disabled = false;
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
  state.overrides = [];
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
  state.template = {
    name: file.name, layouts: result.layouts, masters: result.masters, defaults: result.defaults,
    routes: result.routes, samples: result.samples,
  };
  state.route = result.route;
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
  renderRoute();
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

// Rev 8 (D11): which way the deck is built, and the switch when both ways are on offer.
function renderRoute() {
  const t = state.template;
  const both = t.routes.length > 1;
  $("route").hidden = false;
  const line =
    state.route === "sample" ? fmt(COPY.routeLineSample, { n: t.samples.length }) : COPY.routeLineLayout;
  $("route-line").textContent = both ? `${line}${COPY.routeNote}` : line;
  $("route-switch").hidden = !both;
  $("route-sample").setAttribute("aria-pressed", String(state.route === "sample"));
  $("route-layout").setAttribute("aria-pressed", String(state.route === "layout"));
}

function switchRoute(route) {
  if (!state.template || state.route === route || !state.template.routes.includes(route)) return;
  state.route = route; // the bridge drops every pick made on the other route, each with a note (D11)
  // code review E2: the picks are forgotten now, not at the next successful plan, so an empty or broken outline
  // followed by a switch back can never bring them back; marked "switched", they still reach the bridge only to
  // be dropped there with their note
  state.overrides = state.overrides.map((o) => ({ ...o, route: "switched" }));
  renderRoute();
  staleNow();
  replan();
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
      return JSON.parse(state.session.plan(text, JSON.stringify(state.overrides), state.route));
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
  state.overrides = result.overrides; // a dropped override is forgotten; its note shows once
  renderPlan();
}

function layoutName(id) {
  if (state.route === "sample") {
    const sm = state.template.samples.find((x) => x.id === id);
    return sm ? fmt(COPY.sampleOption, { k: sm.k, words: sm.words }) : id;
  }
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
        // remembered by the slide's title, kind, nth and count, not its index, so it follows the slide
        const same = (o) => o.title === src.title && o.kind === src.kind && o.nth === src.nth;
        state.overrides = state.overrides.filter((o) => !same(o));
        const o = { title: src.title, kind: src.kind, nth: src.nth, count: src.count, layout: sel.value };
        if (state.route === "sample") o.route = "sample";
        state.overrides.push(o);
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
    // the sample route can carry several states on one slide (shrunk, split, warned, check): all are shown
    const flags = s.flags && s.flags.length ? s.flags : [s.fit];
    fit.textContent = flags.map((f) => COPY.fit[f] || f).join(" · ");
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
      out = state.session.fill(text, overrides, state.route);
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
  state.overrides = [];
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
    state.overrides = [];
    state.plan = null;
    $("file").value = "";
    renderTemplate();
    renderPlan();
    $("file").click();
  });
  $("route-sample").addEventListener("click", () => switchRoute("sample"));
  $("route-layout").addEventListener("click", () => switchRoute("layout"));
  $("outline").addEventListener("input", schedulePlan);
  $("download").addEventListener("click", download);
  $("reset").addEventListener("click", reset);
  $("retry").addEventListener("click", boot);

  $("copy-prompt").disabled = true;
  bindCopy($("copy-prompt"), $("copy-prompt-label"), () => state.promptText);
  bindCopy($("copy-link"), null, () => location.href, $("copy-link-done"));
}

function start() {
  applyCopy();
  wire();
  if (PHONE.matches) {
    // The phone view explains and hands over the link; the engine loads if the window widens.
    PHONE.addEventListener("change", () => !PHONE.matches && boot(), { once: true });
    return;
  }
  boot();
}

// Prompt first, then the engine. A prompt that fails to load stops here with the retry state,
// and retry runs this same path again (F9).
async function boot() {
  if (state.loading || state.ready) return;
  setStatus("loading");
  if (!state.promptText) {
    try {
      await loadPromptText();
    } catch (err) {
      console.error(err);
      setStatus("failed");
      return;
    }
  }
  loadEngine();
}

start();
