// Static server for docs/ used by the end-to-end checks. Logs every request it receives.
import http from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../docs");
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm",
  ".zip": "application/zip", ".whl": "application/zip", ".woff2": "font/woff2",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain",
};

export function startServer(port = 0) {
  const log = [];
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://x");
    log.push({ t: Date.now(), method: req.method, path: url.pathname });
    if (url.pathname === "/__probe-worker.js") {
      // test-only: a worker script that would run if the page's policy let it (C9 probe)
      res.writeHead(200, { "content-type": "text/javascript" });
      return res.end("postMessage(1);");
    }
    if (url.pathname === "/__blank") {
      res.writeHead(200, { "content-type": "text/html" });
      return res.end("<!doctype html><title>blank</title>");
    }
    let file = path.join(ROOT, decodeURIComponent(url.pathname));
    if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
    try {
      if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream", "cache-control": "max-age=600" });
      res.end(body);
    } catch {
      res.writeHead(404); res.end("not found");
    }
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve({ server, log, port: server.address().port })));
}
