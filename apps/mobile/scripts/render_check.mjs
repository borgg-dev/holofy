// Headless render check: load the exported web build in a phone-sized Chromium,
// capture console/page errors, and screenshot each main route. Proof the app renders.
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname } from "node:path";

const DIST = process.argv[2] || "dist-web";
const PORT = 8099;
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".png": "image/png", ".ttf": "font/ttf", ".otf": "font/otf",
  ".map": "application/json", ".ico": "image/x-icon" };

// Static server with SPA fallback to index.html (expo-router client routing).
const server = createServer(async (req, res) => {
  const urlPath = decodeURIComponent(req.url.split("?")[0]);
  let file = join(DIST, urlPath);
  try { if ((await stat(file)).isDirectory()) file = join(file, "index.html"); }
  catch { file = join(DIST, "index.html"); }
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": MIME[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(await readFile(join(DIST, "index.html")));
  }
});
await new Promise((r) => server.listen(PORT, r));

const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

const routes = [["/", "01-scan"], ["/vault", "02-vault"], ["/privacy", "03-privacy"]];
for (const [route, name] of routes) {
  await page.goto(`http://127.0.0.1:${PORT}${route}`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `/tmp/holofy_shot_${name}.png` });
  const text = (await page.textContent("body"))?.replace(/\s+/g, " ").trim().slice(0, 140) ?? "";
  console.log(`route ${route.padEnd(10)} -> /tmp/holofy_shot_${name}.png | text: ${text}`);
}

console.log(`\nerrors captured: ${errors.length}`);
for (const e of errors.slice(0, 12)) console.log("  " + e);
await browser.close();
server.close();
