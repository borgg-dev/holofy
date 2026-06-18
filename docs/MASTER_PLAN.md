# Holofy — Master Product & Development Plan

**A Europe-first Pokémon card scanner: valued (€/Cardmarket), verified (anti-counterfeit), pre-graded.**

**Date:** 2026-06-18 · **Status:** Decision-grade v1 · Synthesis of Product, Technical & Design leads
**Working name:** **Holofy** (original, legally-clean; "PokéScan" used in early docs is a placeholder and must NOT be used — "Poké" is Pokémon trade dress)

---

## 1. The product in one paragraph

The card-scanning category is already won on breadth (Collectr: 4M users, US/$/TCGPlayer-native). We do not beat them on breadth — we win a wedge they structurally under-serve: **the European vintage Pokémon collector** who values in **€ via Cardmarket** and fears two specific, expensive things — (a) paying €15–50 + months to grade a card that won't grade well, and (b) owning/buying a fake vintage card. We package **Cardmarket-native € valuation + AI pre-grading + counterfeit detection** as one decision tool, and launch it into the biggest nostalgia wave in the franchise's history: the **30th anniversary**, peaking with the global **30th Celebration set on 16 Sept 2026** (our hard launch anchor).

---

## 2. Positioning (locked)

> **"Scan the Pokémon cards from your childhood and instantly know what they're really worth in euros, whether they're real, and whether they're worth grading — before you spend a cent."**

Three verbs = the entire wedge: **valued · verified · pre-graded.**

- **Primary ICP:** "Returning European Vintage Collector," 28–42, disposable income, just pulled a shoebox of 1999–2003 cards from the attic. **Germany first** (Cardmarket's home, deepest € liquidity), then FR/UK/IT/ES.
- **The moat (all three leads agreed):** NOT any single model — it's the **compounding proprietary dataset** of consented EU-vintage scans + later real PSA/CGC outcome pairs. Architected in from day one.

---

## 3. Market-fit MVP scope (Phase 1 + 2 merged, as requested)

"Smallest build that *proves the differentiated value*" — so pre-grade and anti-fake are IN.

| # | Feature | In MVP? | Note |
|---|---------|:---:|------|
| 1 | Card identification (set, number, **language**, variant) | ✅ | Variant + language detection non-negotiable in EU |
| 2 | **Cardmarket-native € valuation** (+ $ toggle) | ✅ | THE wedge |
| 3 | Collection portfolio + value-over-time | ✅ | Retention engine |
| 4 | **AI pre-grading** (centering/corners/edges/surface + "worth grading?" verdict) | ✅ | Differentiator #1 |
| 5 | **Counterfeit / authenticity scoring** | ✅ | Differentiator #2, hardest to copy |
| 6 | Freemium + subscription + credits | ✅ | Willingness-to-pay is part of validation |
| 7 | Manual search / add (no-scan fallback) | ✅ | Scan misses ~10–15%; prevents day-1 churn |
| 8 | Account + cloud sync | ✅ | A portfolio you can lose isn't one |
| — | Other TCGs, in-app marketplace, social/trade, bulk-binder, grading handoff, price alerts, web app | ❌ v2 | Breadth is the incumbent's game; defer |

**Cut-line:** if it doesn't make €-valuation, pre-grading, or anti-fake believable and sticky, it waits.

---

## 4. Monetization (locked)

| | Free ("Collector") | Premium ("Collector+") | Annual |
|---|---|---|---|
| Price | €0 | **€5.99/mo** | **€49.99/yr** (~€4.17/mo) |
| ID scans | 8/day | Unlimited | Unlimited |
| Pre-grading | 3 credits/mo (the hook) | 30/mo included | + |
| Counterfeit check | 2/mo | Unlimited | + |

- **Credit packs** (high margin, ~€0.01 COGS): 10/€2.99 · 50/€9.99 · 200/€29.99. Anchored vs the real €15–50 + months of actual grading.
- **Affiliate** (Cardmarket/eBay out-links) = minor garnish, not the engine.
- **Unit economics:** ~80% gross margin; break-even ≈ **~9,000 paying subscribers** at ~€40k/mo burn → realistic in the anniversary year.
- Subscription is the engine (€5.99 deliberately undercuts Ludex ~$7.99/Collectr on the exact features they charge more for).

---

## 5. Technical architecture (summary — full detail in `pokescan_technical_architecture.md`)

**Strategy: buy-first / build-later.** Recognition is a cheap commodity (Ximilar ~$0.01/scan); the moat is the data loop that lets us move the common 80% of scans to on-device models at ~€0 marginal cost.

**Stack:** React Native (Expo) + `react-native-vision-camera` + on-device CoreML/TFLite detector · Python/FastAPI backend · PostgreSQL · Redis/SQS async ML stages · S3/Cloudflare R2 · Supabase/Clerk auth · RevenueCat + Stripe billing · **AWS EU region (GDPR data residency)**.

**Three AI pipelines:**
1. **Recognition + variant disambiguation** — buy (Ximilar) + on-device detector; disambiguate ×10 variant errors *deterministically* via set-symbol + bottom-number OCR (where competitors fail). Never silently guess a high-value variant — show top-2 + price delta.
2. **Pre-grading** — build centering in-house immediately (pixel-level, most honest signal); buy corners/edges/surface initially. Output a **grade probability range**, never a single number. Accuracy honestly ~±1 grade in ~95% of cases; surface has a known raking-light blind spot.
3. **Counterfeit** — mostly build (no good commodity API); multi-signal risk score scoped to vintage/high-value. Output "authenticity risk / seek expert review," **never a binary "FAKE"** (reputational + defamation risk).

**⚠️ The two product-killers to settle FIRST (Phase 0 spikes):**
- **Price-data access.** Cardmarket & TCGPlayer direct APIs are effectively closed to new devs. MVP path: consume € + $ pricing **indirectly via aggregator catalog APIs** (Pokémon TCG API/Scrydex, TCGdex) that already legally surface those prices; pursue Cardmarket partner status in parallel. **Legal sign-off required.**
- **Variant disambiguation accuracy** — getting high-value variants wrong destroys trust.

---

## 6. Design & brand (summary — from Design lead)

**Brand: Holofy.** Built entirely on the **holographic foil shimmer** motif — a printing technique, legally clean, NOT Pokémon IP.

- **Concept "Foil Vault":** calm premium near-black "Vault" surfaces (trust, where money is at stake) + reserved **foil shimmer** rewards (joy — reveal, rare pull, milestones). Foil is scarce = special.
- **Palette (distinct from Pokémon yellow/blue):** Holo Violet `#6C3CE0` · Foil Magenta `#FF4FD8` · Vault Teal `#23D5C7` · near-black `#0B0B12`. Signature conic foil-sweep gradient, gyroscope-tilt-reactive.
- **Type (all OFL/free):** Clash Display (headlines) · Manrope (UI, tabular nums for prices).
- **Signature "wow" moments:** scan-frame teal-lock, the foil card reveal (count-up value), pre-grade gauge (range + sub-scores), authenticity shield/amber verdict, portfolio value reveal.
- **Front-end:** RN + Expo · Style Dictionary tokens · ~15 custom brand components (resist generic kits — that's the exact "generic" failure to avoid) · Reanimated 3 + Skia shader for the holo effect.
- **L10n:** FR → ES → IT → DE → EN; `Intl` currency formatting (€1.234,56); +30–35% text expansion (DE).

### ⚠️ Legal line (every lead independently flagged this — highest risk)
The app is a **collector tool**, never a reseller of Pokémon IP. No "Pokémon"/"Poké"/"-dex" in the product name or logo; no character art, Poké Balls, energy/type symbols, or the official typeface in *our* branding. User-photographed cards shown back to the user are fine. Clear "not affiliated with/endorsed by Nintendo/The Pokémon Company" disclaimer. **Legal review of name + store listing + marketing is a hard launch gate.**

---

## 7. The capture↔ML handshake (the one cross-team dependency that makes-or-breaks quality)

Pre-grade & anti-fake accuracy are **gated by capture quality** — these "design" decisions are actually ML requirements:
1. Real-time capture-quality signals (focus, glare %, corner/edge detection) drive the scan-frame teal-lock + coaching chips.
2. The app **refuses to grade** sub-threshold photos and loops back to guided capture.
3. **Multi-angle / raking-light capture** required for surface & holo-signature assessment; rapid/stack mode is **ID + value only** (no grade/auth).
4. Model outputs are always **ranges + sub-scores + confidence** — UI and legal posture depend on probabilistic, explainable outputs.

---

## 8. Unified roadmap to launch (anchor: live & stable before 16 Sept 2026)

| Phase | Window | Goal |
|---|---|---|
| **Phase 0 — De-risk spikes** | ~Jun–Jul | Variant disambiguation accuracy · on-device FPS on mid Android · **legal price-display path** · centering accuracy vs known graded cards |
| **Phase 1 — Core scan loop** | Jul | Capture→recognize→match→€ value→portfolio. Auth, billing, quotas. Closed alpha (50–150 EU collectors) |
| **Phase 2 — Pre-grade v1** | Jul–Aug | In-house centering + bought corners/edges/surface as probability; guided multi-angle capture |
| **Phase 3 — Anti-fake v1 + data loop** | Aug | Authenticity risk score; "log your real grade" + consent-gated data capture; **open beta, Germany-first** |
| **Public launch (multi-EU)** | **Early Sept (before 16 Sept set drop)** | DE/FR/UK/IT/ES live; premium + credits live; creator campaign fires into the anniversary peak |
| **Phase 4+ — iterate / cost-down** | Q4 | Stack/video scanning; move common-card recognition on-device; train pre-grade on real-outcome pairs; eBay graded comps |

**Non-negotiable:** public & stable by the first week of September. Launching after 16 Sept = surfing the wave from behind.

---

## 9. Success metrics — what actually proves market fit

Installs will spike from the anniversary regardless and prove nothing. PMF lives in retention + wedge engagement + willingness-to-pay.

| KPI | Go (PMF) | Kill |
|---|---|---|
| D30 retention | ≥ 25% | < 12% |
| Wedge-feature attach (pre-grade or auth in 1st session) | ≥ 50% | < 25% |
| Free→Paid (30d) | ≥ 6% | < 3% |
| Pre-grade trust (useful / within ±1 grade vs real) | ≥ 80% / ≥75% | < 60% |

**Decision rule:** retention + attach + conversion all green = market fit. Pre-grade trust red = existential (it's the moat).

---

## 10. Top risks (consolidated)

| Risk | Mitigation |
|---|---|
| **Pokémon IP / brand legal** | Tool-not-reseller posture; original "Holofy" brand; disclaimers; legal review pre-launch (hard gate) |
| **Price-data access/licensing** | Consume via aggregators that legally hold display rights; pursue Cardmarket partner status; multi-source fallback |
| **Pre-grade/anti-fake overpromise** | Always ranges + confidence + disclaimers; "pre-screen not a grade," "risk flag not a verdict"; track real match-rate |
| **Me-too vs Collectr** | Speed in the anniversary window + EU-vintage dataset + pre-grade/auth combo they'd have to *build*, not localize |
| **Anniversary = spike not base** | Weight retention/conversion over installs; annual plan + evergreen "attic" messaging to convert the cohort |

---

### Source documents
- `holofy_master_plan.md` (this file — unified synthesis)
- `pokescan_technical_architecture.md` (full technical/AI detail)
- Product Strategy & Design deliverables (in conversation history)
