// Test-only ESM resolve hook: lets `node --experimental-strip-types` run the API
// client's source as-is. The source uses extensionless relative imports (RN/Metro
// convention — `import { x } from "./auth"`), which Node's ESM resolver rejects; this
// appends `.ts`/`.tsx` so the same files the bundler ships are what the tests execute.
// It does not touch the app's runtime — only `npm test` loads it.

import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const CANDIDATES = [".ts", ".tsx", "/index.ts", "/index.tsx"];

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith(".") && !/\.[cm]?[jt]sx?$/.test(specifier)) {
    const base = new URL(specifier, context.parentURL);
    for (const ext of CANDIDATES) {
      const candidate = new URL(base.href + ext);
      if (existsSync(fileURLToPath(candidate))) {
        return nextResolve(candidate.href, context);
      }
    }
  }
  return nextResolve(specifier, context);
}
