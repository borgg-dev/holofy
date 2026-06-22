import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { convertFromEur, formatFromEur, parseCurrency } from "../currency";

describe("currency helpers", () => {
  it("parseCurrency narrows valid values and defaults the rest", () => {
    assert.equal(parseCurrency("EUR"), "EUR");
    assert.equal(parseCurrency("USD"), "USD");
    assert.equal(parseCurrency("GBP"), "EUR"); // unsupported → default
    assert.equal(parseCurrency(null), "EUR");
    assert.equal(parseCurrency(undefined), "EUR");
  });

  it("convertFromEur applies the rate", () => {
    assert.equal(convertFromEur(100, 1), 100);
    assert.ok(Math.abs(convertFromEur(100, 1.1) - 110) < 1e-9);
    assert.equal(convertFromEur(0, 1.08), 0);
  });

  it("formatFromEur converts then formats in the target currency", () => {
    // EUR is identity; the figure is the EUR amount, formatted with the € symbol.
    const eur = formatFromEur(289, "EUR", 1);
    assert.match(eur, /289/);
    assert.match(eur, /€/);

    // USD converts at the rate first (289 × 1.1 = 317.90) and formats with $.
    const usd = formatFromEur(289, "USD", 1.1);
    assert.match(usd, /\$/);
    assert.match(usd, /317/);
    assert.doesNotMatch(usd, /289/); // it is the CONVERTED figure, not the raw EUR one
  });
});
