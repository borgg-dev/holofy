// Registers the test-only TS resolve hook (ts-resolve.mjs) for the current process.
// Used via `node --import ./scripts/register-resolver.mjs` so the resolver runs in the
// same thread before the test files load.
import { register } from "node:module";

register("./ts-resolve.mjs", import.meta.url);
