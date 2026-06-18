// Generates tokens.ts, tokens.css, and a compiled dist/ from tokens.json.
// One source of truth in, consumable artifacts out. Run: node build.mjs
//
// Why a dist/: TS/RN consumers need real JS + .d.ts, not a raw .ts on `main`
// (Metro and tsc would choke on importing the source). We emit:
//   dist/index.js   — ESM, the resolved token tree
//   dist/index.cjs  — CommonJS, for require() call sites
//   dist/index.d.ts — types, so `tokens.color…` autocompletes downstream
import { readFileSync, writeFileSync, existsSync, copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const raw = JSON.parse(readFileSync(join(here, "tokens.json"), "utf8"));

// Resolve {color.x.y} references against the source tree.
const refRe = /^\{([^}]+)\}$/;
function getPath(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}
function resolve(val, seen = 0) {
  if (typeof val !== "string" || seen > 10) return val;
  const m = val.match(refRe);
  if (!m) return val;
  const target = getPath(raw, m[1]);
  return resolve(target?.value ?? target, seen + 1);
}

// Walk the tree collecting leaf tokens (nodes carrying a `value`).
const leaves = [];
function walk(node, path) {
  if (node && typeof node === "object" && "value" in node) {
    leaves.push({ path, value: resolve(node.value) });
    return;
  }
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node)) {
      if (k.startsWith("$")) continue;
      walk(v, [...path, k]);
    }
  }
}
for (const [k, v] of Object.entries(raw)) {
  if (k.startsWith("$")) continue;
  walk(v, [k]);
}

const HEADER = "/* Generated from tokens.json — do not edit by hand. Run build.mjs. */\n";

// ---- tokens.ts : nested, typed object tree ----
function nest() {
  const root = {};
  for (const { path, value } of leaves) {
    let cur = root;
    path.forEach((seg, i) => {
      if (i === path.length - 1) cur[seg] = value;
      else cur = cur[seg] ??= {};
    });
  }
  return root;
}
const ts =
  HEADER +
  "export const tokens = " +
  JSON.stringify(nest(), null, 2) +
  " as const;\n\nexport type Tokens = typeof tokens;\nexport default tokens;\n";
writeFileSync(join(here, "tokens.ts"), ts);

// ---- tokens.css : custom properties under :root, plus a light theme ----
function cssVarName(path) {
  return "--" + path.map((s) => s.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase()).join("-");
}
function cssValue(v) {
  if (typeof v === "number") return String(v);
  if (typeof v === "object" && v !== null) {
    // typographic composite — flatten to sub-vars handled below; skip here
    return null;
  }
  return v;
}

const rootLines = [];
const fontLines = [];
for (const { path, value } of leaves) {
  // Expand typography.scale composites into discrete vars.
  if (path[0] === "typography" && path[1] === "scale" && typeof value === "object") {
    const base = cssVarName(path);
    for (const [k, v] of Object.entries(value)) {
      const sub = k.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase();
      let out = v;
      if (typeof v === "number" && k !== "weight") out = v + "px";
      if (k === "family") out = resolve(raw.typography.family[v].value);
      fontLines.push(`  ${base}-${sub}: ${out};`);
    }
    continue;
  }
  const cv = cssValue(value);
  if (cv === null) continue;
  // Space/radius/size numbers → px; motion durations → ms.
  let out = cv;
  if (typeof value === "number") {
    if (path[0] === "space" || path[0] === "radius") out = value + "px";
    else if (path[0] === "motion" && path[1] === "duration") out = value + "ms";
    else if (path[0] === "size") out = value + (path.includes("ratio") ? "" : "px");
    else out = String(value);
  }
  rootLines.push(`  ${cssVarName(path)}: ${out};`);
}

const css =
  HEADER +
  ":root {\n" +
  rootLines.join("\n") +
  "\n" +
  fontLines.join("\n") +
  "\n}\n\n" +
  "/* Light theme overrides — apply [data-theme=\"light\"] on a container. */\n" +
  "[data-theme=\"light\"] {\n" +
  leaves
    .filter((l) => l.path[0] === "color" && l.path[1] === "semantic" && l.path[2] === "light")
    .map((l) => `  --color-semantic-dark-${l.path[3].replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase()}: ${cssValue(l.value)};`)
    .join("\n") +
  "\n}\n";
writeFileSync(join(here, "tokens.css"), css);

// Mirror tokens.css next to the runnable demos so they stay self-contained.
const demoDir = join(here, "..", "..", "docs", "design", "demos");
if (existsSync(demoDir)) {
  copyFileSync(join(here, "tokens.css"), join(demoDir, "tokens.css"));
}

// ---- dist/ : compiled, importable artifacts (the package's runtime entry) ----
// The .ts is the editing convenience; the dist is what `main`/`exports` resolve to,
// so a consumer never imports raw TypeScript.
const dist = join(here, "dist");
mkdirSync(dist, { recursive: true });

const treeJson = JSON.stringify(nest(), null, 2);

writeFileSync(
  join(dist, "index.js"),
  HEADER + "export const tokens = " + treeJson + ";\nexport default tokens;\n"
);
writeFileSync(
  join(dist, "index.cjs"),
  HEADER + "const tokens = " + treeJson + ";\nmodule.exports = tokens;\nmodule.exports.tokens = tokens;\n"
);

// The .d.ts re-uses the authored tokens.ts `as const` literal so types stay exact
// (each color is its own string-literal type, not a widened `string`).
writeFileSync(
  join(dist, "index.d.ts"),
  HEADER +
    "export declare const tokens: " +
    typeLiteral(nest()) +
    ";\nexport type Tokens = typeof tokens;\nexport default tokens;\n"
);

// Emit a structural .d.ts from the resolved tree: object shapes preserved, leaves
// narrowed to their literal type so downstream code gets real autocomplete.
function typeLiteral(node, indent = 0) {
  const pad = "  ".repeat(indent + 1);
  const close = "  ".repeat(indent);
  if (node && typeof node === "object" && !Array.isArray(node)) {
    const entries = Object.entries(node).map(
      ([k, v]) => `${pad}${JSON.stringify(k)}: ${typeLiteral(v, indent + 1)}`
    );
    return "{\n" + entries.join(";\n") + ";\n" + close + "}";
  }
  if (typeof node === "string") return JSON.stringify(node);
  if (typeof node === "number") return String(node);
  return "unknown";
}

console.log(`Wrote tokens.ts, tokens.css, and dist/ from ${leaves.length} tokens.`);
