import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DEFAULT_THEME_MODE, parseThemeMode, resolveScheme } from "../themeMode";

describe("resolveScheme — mode beats OS only when pinned", () => {
  it("defaults to system", () => {
    assert.equal(DEFAULT_THEME_MODE, "system");
  });

  it("pins light regardless of the OS", () => {
    assert.equal(resolveScheme("light", "dark"), "light");
    assert.equal(resolveScheme("light", "light"), "light");
    assert.equal(resolveScheme("light", null), "light");
  });

  it("pins dark regardless of the OS", () => {
    assert.equal(resolveScheme("dark", "light"), "dark");
    assert.equal(resolveScheme("dark", "dark"), "dark");
    assert.equal(resolveScheme("dark", undefined), "dark");
  });

  it("system is dark-first: only an explicit OS light flips it", () => {
    assert.equal(resolveScheme("system", "light"), "light");
    assert.equal(resolveScheme("system", "dark"), "dark");
  });

  it("system stays dark when the OS scheme is unknown", () => {
    assert.equal(resolveScheme("system", null), "dark");
    assert.equal(resolveScheme("system", undefined), "dark");
  });
});

describe("parseThemeMode — narrows storage reads, never wedges on garbage", () => {
  it("accepts the three valid modes verbatim", () => {
    assert.equal(parseThemeMode("system"), "system");
    assert.equal(parseThemeMode("light"), "light");
    assert.equal(parseThemeMode("dark"), "dark");
  });

  it("falls back to the default for missing or corrupt values", () => {
    assert.equal(parseThemeMode(null), "system");
    assert.equal(parseThemeMode(undefined), "system");
    assert.equal(parseThemeMode(""), "system");
    assert.equal(parseThemeMode("LIGHT"), "system");
    assert.equal(parseThemeMode("midnight"), "system");
  });
});
