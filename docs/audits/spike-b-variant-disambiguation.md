# Audit — Spike B: variant disambiguation

- **Work unit:** Spike B (Phase-0 SPIKE B, variant disambiguation by set + collector number)
- **Auditor:** Independent auditor agent — Architecture + Backend + ML lenses (+ Product/PMF context, Premium gate)
- **Date:** 2026-06-18
- **Artifacts:** `docs/adr/0002-variant-disambiguation.md`; `spikes/variant_disambiguation/{variant_spread.py,test_variant_spread.py,README.md,requirements.txt,FINDINGS.md}`
- **Charter:** `DEVELOPMENT_CHARTER.md` §3.1, §3.2, §3.3, §3.6

## Method

Inspected all five artifacts plus `TECHNICAL_ARCHITECTURE.md` §3.1 and the sibling Spike A
(`spikes/price_fetch/`) for copy-paste drift. Ran the suite and the tool live.

- **Tests:** `python3 -m pytest -q` → **13 passed in 0.12s**, hermetic (network mocked via
  `httpx.MockTransport`, no live calls).
- **Live tool:** `httpx 0.27.2` imports; `api.tcgdex.net` reachable, no key.

Verified the central claim against the **live** API (not just the captured README table):

| Claim (README / ADR / FINDINGS) | Live value (2026-06-18) | Match |
|---|---|---|
| ~31 printings named exactly "Charizard" | 32 enumerated (1 added since capture) | ✓ (drifted +1, see F4) |
| spread €1.95 → €4,043.40 = ×2,074 | identical, to the cent | ✓ |
| Skyridge 146/144 dearest at €4,043.40 | top row, full unbounded run | ✓ |
| Base Set 4/102 €757.10 (1st Ed) | present, €757.10 | ✓ |
| Base Set 2 4/130 €255.57 (Holo) | present, €255.57 | ✓ |
| Evolutions 11/108 €238.85 — same Arita art | present, €238.85 | ✓ |
| Secret Wonders €70.53 holo / €38.70 reverse (FINDINGS:76) | `trend: 70.53`, `trend-holo: 38.7` | ✓ |
| unknown name → exit 2 | `Mewthree` → "No card named…" exit 2 | ✓ |
| degrades to "no Cardmarket data", never €0 | 5 unpriced rows render so | ✓ |

The central claim — *printings of one exact name, often sharing the exact artwork, carry an
order-of-magnitude € spread separable only by `(set symbol + collector number)`* — is
**true, reproducible, and quantified against a live catalog**, not asserted. The
Base/Base 2/Evolutions identical-art trio is the load-bearing example and it holds.

---

## Lens: Architecture (§3.2)

| Criterion | Score | Notes |
|---|---|---|
| Fits documented design; ML stages swappable (buy→build) | 3 | ADR maps cleanly to `TECHNICAL_ARCHITECTURE.md` §3.1: recognise→read→resolve→gate. Names a `VariantResolver` contract `(candidate names, OCR'd collector string, set hint, variant cues) → ranked cards + confidence` (ADR:70-77); read side (Ximilar→on-device) swaps without touching the resolver. Seam is explicit. |
| Clear boundaries, no leaky coupling / no premature abstraction | 3 | Spike is one module, one public function (`enumerate_printings`), one domain exception, two frozen-slots dataclasses. The `VariantResolver` interface is correctly *deferred to production*, not built into the throwaway (ADR:101 calls `enumerate_printings` the "embryonic catalog side"). Right altitude. |
| Data-capture/consent loop honored (the moat) | 2 | Not a user-content path in the spike, so consent N/A here. The moat hook — the top-2 confirm tap becomes a labelled training example — is explicit and tied to the on-device migration (ADR:93-94, FINDINGS:50-51). Honored to the extent the slice touches it. |
| Decisions traceable to an ADR | 3 | ADR 0002 is well-formed: status, deciders, three options with explicit verdicts, ordered decision, consequences, references, and the internal `[DEP: Design]` blocker raised honestly (ADR:100-112). Cross-links ADR 0001, §3.1, and the spike artifacts. Exemplary. |

**Lens average: 2.75 — every criterion ≥2 → PASS.**

---

## Lens: Backend (§3.3)

| Criterion | Score | Notes |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | `from __future__ import annotations`, full type hints, frozen+slots dataclasses, `Final` constants, `Decimal` for money (never float). Sync `httpx.Client` with injectable client for testability; no async needed for a CLI spike, correctly not forced. House style matches Spike A. |
| Real error handling, validation, observability — not happy-path | 2 | Domain `CardNotFound` (exit 2) and `httpx.HTTPError` (exit 1) both handled in `main` with stderr + distinct exit codes (variant_spread.py:256-261); 404 on a stale stub id would surface as `HTTPStatusError` → exit 1, acceptable for a spike. Minor: no per-card resilience — one failed detail fetch aborts the whole enumeration (F2). No timeout retry, fine at this altitude. |
| Tests: unit for logic, integration for contract. Green | 3 | 13 tests, hermetic via `MockTransport` routing both the list and detail endpoints from an in-memory catalog (test_variant_spread.py:56-70). They pin real behaviour — variant priority resolution (parametrized), ×N spread maths to a checked figure (×374.8), unpriced exclusion, dearest-first ordering, exact-name routing, `set_code` promo fallback, `_to_decimal` float-noise. Not trivial; each asserts a distinct property the ADR reasons about. Green. |
| No secrets; EU data-residency & GDPR primitives | 3 | No key, no secret, no PII. Reads a public EUR catalog (Cardmarket via TCGdex) — EU-origin price data, consistent with ADR 0001. N/A surface handled cleanly. |

**Lens average: 2.75 — every criterion ≥2 → PASS.**

---

## Lens: ML / data-honesty (read against §3.1 honesty bar)

| Criterion | Score | Notes |
|---|---|---|
| Disambiguation hypothesis is the right one & proven | 3 | Collector-number-primary, set-symbol-corroborates is correct domain reasoning: the implied set total ("/102" vs "/130" vs "/108") separates the near-identical-symbol WotC reprints more robustly than symbol pixels (ADR:73-74, FINDINGS:30,67). Proven against live data. |
| Accuracy estimate honest, sourced, not inflated | 3 | Two-stage budget stated as ranges with the failure mode named: recognition ~97–98% top-1 *image* (explicitly "name not price"), OCR ~98–99% clean but **~80–90% on phone photos**, degraded by holo glare + vintage ink wear (FINDINGS:26-31). Each row sourced (Ximilar docs, Tesseract/extend.ai OCR-limits guide, set-symbol classification article). No absolute claims; the headline is "clean capture resolves; degraded capture is where we must not guess." This is the honest framing §3.1 demands. |
| Failure handled by gate, not by silent guess | 3 | The "never silently emit a high-value variant" rule is structural: resolver always returns a *ranked* result with confidence, UI auto-confirms or shows top-2 + € delta (ADR:74-77, FINDINGS:46-55). Converts the ×100 mispricing into a cheap one-tap confirm. Matches §3.1 (ranges + confidence, never absolute) and §3.5 anti-fake posture. |
| Known gaps tracked honestly, not hidden | 3 | Reverse-vs-holo is correctly called *not OCR-resolvable* (same symbol+number; needs foil cue/prompt) and the spike's own `trend-holo` evidence backs it (FINDINGS:75-79, verified live: Secret Wonders 70.53/38.70). Promos/alphanumeric numbers and language splits flagged as bounded gaps, not blockers. The capture-quality ceiling is escalated to `[DEP: Design]` rather than glossed. |

**Lens average: 3.0 — every criterion ≥2 → PASS.**

---

## Premium / Not-Generic gate (§3.6) — zero-AI-tell scan

| AI-tell category | Finding |
|---|---|
| Generic/stock look, placeholder copy | None. CLI output is domain-precise and tasteful (`×vs floor`, `VARIANT TUPLE`, aligned columns). No lorem/TODO. |
| Over-commenting / narrates *what* | None. Comments explain *why* (the `-holo` reverse-holo subtlety variant_spread.py:36-38; the `eq:` decoy exclusion :138-142; the sort intent :193). No what-narration. Notably *less* commented than the duplicated helper in Spike A — drift in the good direction. |
| Speculative abstraction / dead code / `handleData`/`foo`/`temp` | None. Naming is domain-precise (`enumerate_printings`, `tuple_label`, `dearest`, `set_code`). No dead code, no unused params. `product_id` is carried but unused in render — it's the Cardmarket join key the production resolver needs, defensible to keep. |
| Boilerplate/marketing voice, em-dash hype, emoji-decoration | None. README/FINDINGS are dense and engineering-voiced. Em-dashes used as punctuation, not hype-soup. No emoji. The "Is / Isn't" section is restraint, not marketing. |
| Inconsistent house style / tutorial-grade | None. Style is identical to Spike A (same header pattern, `Final`, `Decimal`, injectable client, exit-code convention). Reads as one author's deliberate house style across the spike suite. |
| Missing unglamorous polish / edge cases | Handled: promo total-less `set_code` fallback, unpriced sink-to-bottom, exact-name `eq:` filter, `Decimal` currency, distinct exit codes, hermetic tests. The unglamorous bits are present. |

**AI-tells found: ZERO. Every applicable criterion ≥2.**
**Premium gate: PASS.** A top-tier studio would ship this as a Phase-0 spike: it proves the
claim against live data, the resolver contract it implies is clean and swappable, the
accuracy story is honest and sourced, and the failure mode is engineered into a safe outcome
rather than hidden.

---

## Prioritized findings

All findings are **minor / non-blocking** (spike altitude). None fails any lens.

- **F1 — `--limit` truncates *before* sorting, so it can hide the dearest printing (and the
  headline spread). `variant_spread.py:188-189,170-173`.** `_capped` slices the unsorted
  stub list, then printings are sorted dearest-first. Live-confirmed: `--limit 12` drops
  Skyridge €4,043 and reports ×388 instead of ×2,074 — i.e. the limited run *understates the
  exact problem the spike exists to prove*. The README run is unbounded so its table is
  correct, but the README docstring at line 161-162 claims "the dearest few are what the
  disambiguation UX actually shows," which is the opposite of what `--limit` does. Cheap fix:
  fetch all, sort, then cap; or document `--limit` as "first N catalog stubs, unordered."
  **Severity: low** (cosmetic for a spike, but mildly misleading). 

- **F2 — Enumeration is all-or-nothing on detail fetches. `variant_spread.py:170-173`.** A
  single `raise_for_status` failure on one of ~32 follow-up calls aborts the whole spread.
  Fine for a throwaway; the production resolver should tolerate a partial catalog read.
  **Severity: low.**

- **F3 — `_to_decimal` / `API_ROOT` / `_REQUEST_TIMEOUT` / `CardNotFound` are duplicated
  from Spike A (`price_fetch/tcgdex_prices.py:21-22,62-67`).** Acceptable for independent
  throwaway spikes (no shared package yet), and the variant copy dropped the explanatory
  comment in favour of a named test (`test_to_decimal_avoids_binary_float_noise`) — good
  drift, not bad. Flagged only so the production refactor folds these into one TCGdex client
  module. **Severity: informational.**

- **F4 — Captured README table says "31" / "all 31 exact-name printings"; live now returns
  32 (`README.md:63`, `FINDINGS.md:11`).** The catalog grew by one printing since the
  2026-06-18 capture (Crimson Blaze now contributes a second Charizard). The €/×2,074
  headline is unaffected. Worth a "captured YYYY-MM-DD, count may drift" note, which the
  README already half-does ("captured 2026-06-18"). **Severity: informational.**

- **F5 — `_VARIANT_PRIORITY` can mislabel a card whose primary printing is reverse-only.
  `variant_spread.py:38-44,112-116`.** Holo is prioritised above reverse, so a card flagged
  both shows "Holo" — correct for vintage rares, but the within-card reverse split the ADR
  itself calls out (and which the live Secret Wonders data exposes via `trend-holo`) is *not*
  represented in the single-`variant` `Printing`. The spike correctly does **not** claim to
  resolve it (FINDINGS:75-79 names it a known gap), so this is consistency-with-its-own-scope,
  not a defect. **Severity: informational.**

---

## Verdict

| Lens | Average | Min criterion | Result |
|---|---|---|---|
| Architecture (§3.2) | 2.75 | 2 | **PASS** |
| Backend (§3.3) | 2.75 | 2 | **PASS** |
| ML / data-honesty (§3.1) | 3.00 | 3 | **PASS** |
| Premium gate (§3.6) | — | all ≥2, 0 AI-tells | **PASS** |

**Overall: PASS on every applicable lens and the Premium gate.** The core claim is verified
live (×2,074 spread on identical-artwork printings, separable only by collector-number+set).
Tests are hermetic and meaningful (13/13). The accuracy estimate (~80–90% phone-photo OCR) is
honest, ranged, and sourced. Zero AI-tells. The five findings are all spike-altitude polish
items; none blocks the build-approval the ADR already carries. **No refine cycle required.**
Recommend carrying F1 (limit/sort) and F3 (shared TCGdex client) into the production backlog.

---

## Refine note (orchestrator, 2026-06-18)
F1 fixed: `--limit` no longer misrepresented as selecting "the dearest few" — docstring + CLI help now state it samples in catalog order and may understate the spread (the unbounded default proves the full range). Suite still green (13 passed). F3 (shared TCGdex client) deferred to the production pricing service. Gate was already PASS.
