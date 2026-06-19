# Holofy — Live Status

**Updated:** 2026-06-19 · **Phase:** GOING REAL (Pokémon-only) — all 5 units built; device validation pending · **Launch anchor:** before 2026-09-16

## Pokémon-only "make it real" build (started 2026-06-19)
Focus narrowed to **Pokémon only** (defer multi-category; keep architecture scalable). Dev
parts first, no Ximilar key yet. Five units (task backlog): (1) real capture→upload→storage,
(2) "is this a Pokémon card?" guard, (3) card identification (keyless Spike-B path + Ximilar
adapter behind seam), (4) pre-grade on real input + Ximilar grading adapter, (5) mobile off
fixtures onto live API.

**Unit 3 — in-house identification GENUINELY BUILT & verified ✅ (real pixels → identity):**
- Owned module `app/identify/`: collector-number parse/match (Spike-B's disambiguator —
  full number pins a printing, numerator-only narrows → confirm), `CatalogIndex` seam +
  `InMemoryCatalogIndex`, `CardResolver` (read-quality-capped scoring → ranked result).
- **Real vision stage** `app/identify/vision/`: numpy card detect/crop (`detect.py`) + a
  genuine OCR engine (`ocr.py`, RapidOCR / ONNX — pure-pip, CPU, no system Tesseract, no
  per-scan vendor fee) + `VisionCardReader` parsing number/name from located tokens.
- `RecognitionBackend.INHOUSE` wired into config + factory + lifespan; `InHouseRecognitionProvider`
  composes store → detect → OCR → resolve behind the standard seam.
- **Proven end-to-end over HTTP** (`test_inhouse_scan_e2e`): upload a real card PNG → `/scan`
  (inhouse) → OCR reads the pixels → resolves `origins-8` "Tidecaller Leviath" → priced. No
  fixtures, no network, no Ximilar. 201 backend tests (+14); real-OCR tests marked `ocr`.
- **Real TCGdex catalog** `app/identify/tcgdex_catalog.py`: name search → numerator pre-filter
  → per-card detail → `CatalogCard` (set, total, variant). Selectable via `HOLOFY_CATALOG_PROVIDER`
  (`inmemory` default | `tcgdex`); the recognizer factory returns its pooled client for the
  lifespan to close, like pricing. Hermetic tests via `httpx.MockTransport`. 206 backend tests.
- **Remaining:** production fronts the live catalog with the nightly Postgres sync (same seam);
  real-photo OCR accuracy (vs synthetic) is device-validated later — capture quality is the ceiling.

**Live owned-models journey ✅** — `make api-smoke-inhouse` boots the API on the in-house
recognizer + grader and drives the whole journey over HTTP on real uploaded card images:
presence guard rejects a non-card (422), a clean card resolves + prices from real pixels, an
ambiguous "12" reprint routes to confirm (€757 vs €24), and a capture pre-grades to an honest
range (centering/corners/edges/surface measured). The fast mock `api-smoke` is unchanged.

**Unit 2 — Pokémon-card presence guard done & verified ✅:**
- `app/identify/presence.py`: `CardPresenceProvider` seam + `HeuristicCardPresence` (v1 from
  card-detection quality). Rejects a hand / table / random object / undecodable frame before
  the recognizer spends an OCR pass; the trained Pokémon/multi-game classifier drops in behind
  the same `assess`. Wired into `InHouseRecognitionProvider` (guard → skip OCR when absent).
  Verified: framed card accepted, non-card rejected, OCR skipped when absent. 217 backend tests.

**Unit 4 — in-house grading GENUINELY BUILT & verified ✅ (real pixels → range):**
- `app/grading/condition.py`: classical-CV corners/edges/surface reader — measures defect
  *roughness* (edge whitening/fraying, surface scratches) from the detected card crop, maps
  to 1–10 with honestly **modest** confidence (a v1 heuristic, improved by the data loop).
- `InHouseGradingProvider` behind the standard `GradingProvider` seam; `GradingBackend.INHOUSE`
  wired through config/factory/lifespan. Composes with the already-real centering.
- Verified: clean card reads high, real edge/surface damage drops *that* axis; and an HTTP
  e2e (`test_inhouse_pregrade_e2e`) — upload real card → `/pregrade` (inhouse) → estimated
  range from real centering + real condition, honest framing intact. 212 backend tests.

**Unit 5 — mobile points at the live API ✅:** the root layout uses the HTTP client when
`EXPO_PUBLIC_API_URL` is set (`EXPO_PUBLIC_DEV_TOKEN` for the bearer), else the fixture client
(demo default). Same screens, real backend — no screen changes. tsc 0, 160 mobile tests.

**Unit 1 — camera capture wired ✅ (device-runtime validation pending):**
- `useCardCapture` hook (expo-camera `CameraView` + permissions + `takePictureAsync`) with a
  web/demo fallback to the stand-in preview + a marker capture. `CameraPreview` renders the
  live camera when permitted, the placeholder otherwise. Scan flow is now one genuine path:
  **capture → `uploadCapture` → `runScan(ref)`** on device (real camera + server) and in the
  demo (fixture mints + cycles refs so both outcomes still show). `tsc` 0, 160 mobile tests,
  and the **web export builds** (so `make mobile-watch` is safe). Native camera runtime is the
  one piece only a device/simulator can validate.

**Unit 1 — backend + mobile upload seam done & verified ✅:**
- New `CaptureStorage` seam (`app/storage/`) with `memory` + `local` backends holding real
  uploaded bytes; `mock` (synthetic-by-ref) stays the default for tests. Config-selected
  (`HOLOFY_CAPTURE_STORAGE`); EU S3/GCS drops in behind the same Protocol.
- `POST /captures` upload endpoint (auth + ingress guards) → returns the `ref` that `/scan`
  and `/pregrade` carry. 187 tests green (+12).
- `make api-smoke` now uploads a real still and runs pre-grade/authenticity against the
  stored bytes (`HOLOFY_CAPTURE_STORAGE=memory`). Pinned missing deps (python-multipart,
  fakeredis[lua], async-timeout). Toolchain note: backend needs Python ≥3.11.
- Mobile API client: `uploadCapture()` (multipart) on `HolofyClient` — HTTP + fixture
  impls, typed `capture_rejected`/`capture_upload_unavailable` errors. 159 mobile tests
  green, `tsc` 0. Toolchain note: mobile test/typecheck need Node ≥22 (`--experimental-strip-types`).
- **Remaining for Unit 1 (own sub-slice, needs device verification):** replace the
  `CameraPreview` placeholder with expo-camera `CameraView`, capture stills on the locked
  shutter, call `uploadCapture`, pass the returned ref into `runScan`. Must keep
  `make mobile-watch` (web/fixtures, no real camera) working — graceful fallback required.

## 🏁 The autonomous mock-first product is FINISHED
All features built + audited; backend runs live (`make api-smoke`, 175 tests); mobile builds reproducibly (android+web, `make mobile-watch`, 135 tests, tsc 0); productionization scaffold authored + CI-verified. What remains to go **real/launchable** is founder-gated — see **BLOCKERS.md** (Ximilar/pricing keys, auth+billing choices, EU cloud + capture storage, Apple/Google accounts, and 2 legal gates). Phase 5 retro: `docs/PHASE_5_RETRO.md`.
P5.2 (real Ximilar/OAuth/billing adapters) deliberately NOT built — speculative + unverifiable without keys; seams are ready. Honesty note: the sandbox has no Docker/Postgres/Redis/browser, so those run in CI, not here.


## DEV-MODE STATUS — HONEST (verified 2026-06-18)
- **Backend: ✅ genuinely runs.** `make api-smoke` boots a fresh API and drives the whole product over HTTP — scan (incl. live €732.60 confirm), stack scan, collection, portfolio, pre-grade range, authenticity (no verdict), account-level consent — mock-first, no keys. 170 tests. Verified by running it.
- **Mobile: ✅ NOW BUILDS (reproducibly).** Root cause of the never-built app was found + fixed: the OFL fonts were gitignored (so never in the repo) and a transitive dep was missing. After vendoring the fonts + deps, from a **clean install of committed code**: `npx expo export` succeeds for **android** (1296 modules, Hermes bundle) AND **web** (1025 modules, servable — index 200, 1.78MB JS loads); `tsc` 0; 135 tests. Build targets: `make mobile-build` / `make mobile-web`.
  - **Remaining (honest):** the rendered screens have NOT been eyeballed in a browser/simulator from here (no headless browser available). The web build serves and the bundle loads, but "screens visually render correctly" is unconfirmed until someone opens `make mobile-web` output or runs `npx expo start`. Not claiming that as done.

The autonomous **mock-first roadmap is essentially complete**: full MVP (scan/value/portfolio/pre-grade/anti-fake/data-loop) + stack scanning, all behind swappable seams. Next steps split into autonomous productionization vs founder-gated mocks→real activation.

## Phase 4 — Stack scanning + dev-mode ready: COMPLETE ✅ (retro: docs/PHASE_4_RETRO.md)
| Unit | What | Status |
|------|------|--------|
| dev-smoke | Live end-to-end journey over HTTP + Makefile + DEV_RUNBOOK | ✅ |
| P4.1 | /scan/batch: dedupe + COGS-safe charge-before-recognize (failed audit on COGS → refined → proven) | ✅ 170 tests |
| P4.2 | Mobile rapid scan: filmstrip + dedupe-merge + confirm-at-end + bulk add | ✅ 135 tests |

## Phase 5 — Productionization (next)
| Unit | What | Status |
|------|------|--------|
| P5.1 | Docker/compose (api+Postgres+Redis), real Redis limiter, run on Postgres, CI, env templates — autonomous, no keys | next |
| P5.2 | Real provider adapters (Ximilar/pricing/OAuth/billing) behind seams, contract-tested, activation gated on keys | next |

**Mocks→real activation needs the founder** (BLOCKERS.md): API keys/accounts, billing+OAuth provider choices, EU cloud, legal price-display clearance, expo-camera. Each is a config/seam swap, not a rewrite.

## MVP feature set: COMPLETE (mock-first) ✅
The full market-fit MVP runs end-to-end on mocks: scan → identify → € value (Cardmarket-native) → confirm low-confidence variants → portfolio → pre-grade (range+confidence) → authenticity (risk band, no verdict) → consented data loop. All behind swappable provider seams. The BLOCKERS (legal price-display clearance, Ximilar/aggregator keys, dev accounts, billing, OAuth, Redis, expo-camera) gate only the mocks→real switch, not the build.

## Phase 3 — Anti-fake + data loop: COMPLETE ✅ (retro: docs/PHASE_3_RETRO.md)
| Unit | What | Status |
|------|------|--------|
| P3.1 | Authenticity risk-score service (no binary verdict; catalog cross-check; value-gated) | ✅ done (130 tests) |
| P3.3 | Consented data loop: DataLakeSink + account-level consent UX (single emit gate) | ✅ done (148/73) |
| P3.2 | Mobile authenticity verdict (shield/amber, separated evidence-quality) | ✅ done (106 tests) |

Hard gates held: no-verdict/defamation (4-layer structural) + privacy/consent (single gate, default off).

## Next: hardening pass (P3.h) → Phase 4 (stack scanning)
| Unit | What | Status |
|------|------|--------|
| P3.h | Clear accumulated audit debt (#11): signal.detail content contract, image_count, CORS, indexes, error mapping, consent-UI tests | next |
| P4.1 | Backend stack/batch scan (dedupe + confirm-at-end) | after P3.h |
| P4.2 | Mobile rapid scan mode (filmstrip + bulk add) | blocked by P4.1 |

## Phase 2 — Pre-grade v1: COMPLETE ✅ (retro: docs/PHASE_2_RETRO.md)
| Unit | What | Status |
|------|------|--------|
| P2.1 | Pre-grade backend: in-house centering + mocked grading seam → grade probability range + confidence; /pregrade; refuse-on-bad-capture | ✅ done (99 tests) |
| P2.2 | Mobile: guided multi-angle capture + bespoke SVG range-band gauge + retake | ✅ done (64 tests) |
| P2.cleanup | Mobile compiles clean under tsc --strict (7→0) | ✅ done |

Honest-framing enforced structurally (no `grade` field anywhere; range + P(≥X) + confidence; worst-axis gating; refuse-on-bad-capture; amber-never-red). Verified by adversarial audit sweep.

## Phase 3 — Anti-fake v1 + data loop (next)
| Unit | What | Status |
|------|------|--------|
| P3.1 | Authenticity risk-score service (mock-first; never binary "FAKE") | next |
| P3.2 | Mobile authenticity verdict flow (shield/amber, never red FAKE) | blocked by P3.1 |
| P3.3 | Data loop: consent UX + capture→data-lake seam (the moat) | next (parallel-ok) |



## Phase 1 — core scan loop: COMPLETE ✅ (retro: docs/PHASE_1_RETRO.md)
| Unit | What | Status |
|------|------|--------|
| P1.1 | Backend skeleton + swappable mock providers + consolidated TCGdex pricing + /scan | ✅ done (27 tests) |
| P1.2 | Persistence: models + Alembic + consent/erasure (privacy-by-design) | ✅ done (+14 tests) |
| P1.3 | RN/Expo scaffold on compiled design tokens + scan-frame screen | ✅ done (no veto) |
| P1.4 | Vertical slice: auth + rate-limit + persisted scan + collection/portfolio; Reveal/Confirm/Vault screens | ✅ done (backend 60, mobile 26) |

The core scan loop runs end-to-end on mocks: scan → identify → € value → confirm (if low-confidence) → add to Vault → portfolio. Auth secret hardened; **all Pokémon IP removed from shipped mock data** (invented cards, 30.9× split preserved).

## Phase 2 — Pre-grade v1 (next)
| Unit | What | Status |
|------|------|--------|
| P2.1 | Pre-grade service: Spike-D centering in-house + mocked grading seam → grade probability range + confidence | next |
| P2.2 | Mobile: guided multi-angle capture + pre-grade gauge screen (range + sub-scores + disclaimer) | blocked by P2.1 |

Carried non-blocking polish: tasks #6 (design) + #11 (backend/mobile findings) — apply during Phase 2.


> Resume point for any session: read this file + `DEVELOPMENT_CHARTER.md` + the task backlog.

## Current phase: Phase 0 — De-risk spikes
Settle the two product-killers and two technical unknowns *before* committing real build effort (and money), per the charter loop (Plan→Build→Audit→Gate).

| Spike | Question | Status |
|-------|----------|--------|
| A — Legal price-data path | Is there a legal, reliable € (Cardmarket) price source via aggregators? | ✅ done (gate PASS) |
| Design foundation | Holofy design-token system + signature-screen spec, audited to Premium bar | ✅ done (gate PASS) |
| B — Variant disambiguation | Can set-symbol + bottom-number OCR reliably catch ×10 variant errors? | ✅ done (gate PASS) |
| C — On-device detection FPS | Real-time card detection on mid-range Android? | ✅ done (gate PASS) |
| D — Pre-grade centering | Pixel-level centering accuracy vs known graded cards? | ✅ done (gate PASS) |

## Done
- Master plan, technical architecture, design system synthesized (`docs/`).
- Development charter + autonomous build–audit loop defined.
- Repo + structure + backlog initialized.
- **Spike A (price-data):** technical € path PROVEN via TCGdex (live fetch, Charizard €757.10); decision = Scrydex primary + TCGdex fallback (ADR 0001). Commercial-display legal clearance still pending (see BLOCKERS).
- **Design Foundation:** bespoke "Foil Vault" token system (144 tokens, TS+CSS) + 3 signature-screen demos. Premium gate PASS (no veto).

- **Spike B (variant disambiguation):** PROVEN — 31 printings named "Charizard" span €1.95→€4,043 (×2,074); identical-art printings separable only by collector-number+set. Pipeline: recognise→OCR number+classify symbol→resolve→low-confidence shows top-2 with € delta. OCR on phone photos ~80–90% (capture-quality gated). ADR 0002.
- **Spike C (on-device FPS):** FEASIBLE — YOLO11n @320px int8, ~20–30 FPS mid-range, stack mode ~75–100 cards/min even on fallback tier. Riskiest unmeasured number: mid-range latency (~32ms, on the 30 FPS knife-edge) — settle on real hardware. ADR 0003.
- **Spike D (pre-grade centering):** WORKS — pure-numpy pixel-level centering, 0px error on 400 synthetic cards, honest confidence (measurement-quality, not centering-quality). Hard dependency: needs deskewed/flat capture (perspective is the top real-world risk). `spikes/centering/`.

## Phase 0 verdict: GREEN — no plan-level forks
All four de-risk questions resolved positively. Both product-killers cleared technically (price path proven; variant disambiguation proven). One unresolved item is **legal, not technical**: commercial-display clearance for aggregator-sourced € prices (BLOCKERS). Recurring theme across spikes: **capture quality is the universal accuracy ceiling** — the guided-capture scan-frame is a hard cross-team dependency for recognition, OCR, centering, and anti-fake alike.

## In flight
- Phase 0 retro (next) → Phase 1 kickoff (core scan loop).

## Last audit results (Phase 0 iteration 2)
- Spike B: Architecture/Backend/ML + Premium PASS (zero AI-tells). `docs/audits/spike-b-variant-disambiguation.md`.
- Spike C: Architecture/ML + Premium PASS (numbers re-derived from the helper, sourced). `docs/audits/spike-c-on-device-fps.md`.
- Spike D: lenses PASS; Premium gate conditional → 1 dead-code AI-tell fixed → PASS. `docs/audits/spike-d-centering.md`.

## Next
- Write Phase 0 retro. Then Phase 1 (core scan loop). **Phase 1 integration will hit BLOCKERS** (Ximilar key, aggregator tier, dev accounts, legal) — surface batched before real-service wiring; build against mocks meanwhile.
