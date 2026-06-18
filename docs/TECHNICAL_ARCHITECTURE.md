# PokéScan — Technical Architecture & AI/ML Plan (MVP 2026)

**Author:** Technical Architecture & AI/ML Lead
**Status:** Decision-grade draft, v1 (merges with Product Strategy + Design deliverables)
**Scope:** Engineering, AI/ML, infrastructure. Hard dependencies on Product/Design are flagged inline as **[DEP]**.

---

## 0. Executive summary (read this first)

We can ship a market-fit MVP in 2026 with **pre-grading and anti-counterfeit included in v1**, on a buy-first / build-later strategy. Three findings shape the whole plan:

1. **Recognition is a solved, cheap commodity.** Start by buying Ximilar (~$0.01/scan) and/or self-hosting a Roboflow/YOLO detector. We do **not** build recognition from scratch on day one.
2. **Pricing data is the real legal/operational risk, not recognition.** Both the **Cardmarket API and TCGPlayer API are effectively closed to new developers** (Cardmarket gates behind commercial-seller verification; TCGPlayer stopped onboarding in late 2024 after the eBay acquisition). The pragmatic path is to **consume Cardmarket EUR + TCGPlayer USD pricing indirectly** via aggregator catalog APIs (Pokémon TCG API / Scrydex, TCGdex) that already legally surface those price points, then layer eBay sold-comps later for graded-card valuation.
3. **Pre-grading and anti-counterfeit are buy-then-build, and they are honest "decision support," not authority.** Realistic AI accuracy is ~±1 PSA grade in ~95% of cases, with a known blind spot on **surface defects only visible under raking light**. We must message this as "pre-screen before you pay for grading," never "this is a grade." **[DEP: Product]** must own that framing; **[DEP: Design]** must own the guided-capture UX that makes pixel-level centering and surface inspection possible.

The moat is **not** the first model — it is the **proprietary labelled dataset** that our own scans + later real PSA/CGC outcomes generate. The architecture is designed from day one to capture that data legally and turn it into in-house models that cut per-scan COGS toward zero.

---

## 1. System architecture

### 1.1 Component diagram (text)

```
┌──────────────────────────── MOBILE APP (React Native + on-device ML) ───────────────────────────┐
│                                                                                                  │
│  Camera / Capture ──► On-device detector (YOLO/RF-DETR via CoreML/TFLite)                         │
│        │                   │  - locate + de-skew card in frame                                    │
│        │                   │  - quality gate (blur, glare, framing, lighting)  ◄── guided capture │
│        │                   │  - cheap "is this a card?" + rough class (offline-first)             │
│        ▼                   ▼                                                                       │
│  Capture bundle: 1..N high-res stills + crops + frame metadata (no raw video stored by default)   │
│        │                                                                                          │
└────────┼─────────────────────────────────── HTTPS / mTLS ─────────────────────────────────────────┘
         ▼
┌──────────────────────────────────────── BACKEND (API gateway) ───────────────────────────────────┐
│  Auth (Clerk/Auth0/Supabase Auth)   Rate-limit / quota / abuse guard   Billing (Stripe/RevenueCat)│
│                                                                                                   │
│  ┌────────────┐   enqueue   ┌──────────────── Async job queue (SQS/Redis) ─────────────────┐      │
│  │ App API    │────────────►│  workers: recognize → match → value → pregrade → fakecheck   │      │
│  │ (REST/GQL) │◄────────────│  (each stage independently scalable / swappable)             │      │
│  └─────┬──────┘   results   └───────┬───────────────┬───────────────┬───────────────┬──────┘      │
│        │                            ▼               ▼               ▼               ▼             │
│        │                  ┌─────────────┐  ┌──────────────┐ ┌─────────────┐ ┌─────────────┐       │
│        │                  │ Recognition │  │   Pricing    │ │  Pre-grade  │ │  Anti-fake  │       │
│        │                  │  service    │  │   service    │ │   service   │ │   service   │       │
│        │                  │ (Ximilar /  │  │ (cache +     │ │ (Ximilar    │ │ (in-house   │       │
│        │                  │  own model) │  │  aggregator) │ │  grade API/ │ │  CNN +      │       │
│        │                  └─────────────┘  └──────────────┘ │  own CNN)   │ │  heuristics)│       │
│        ▼                                                    └─────────────┘ └─────────────┘       │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────────────────────────────┐         │
│  │ Postgres     │   │ Object storage   │   │ Pricing cache (Redis + Postgres history)    │         │
│  │ users,       │   │ (S3) user photos │   │ daily/hourly refresh from aggregator feeds  │         │
│  │ collection,  │   │ + model crops    │   └────────────────────────────────────────────┘         │
│  │ portfolio,   │   └──────────────────┘                                                          │
│  │ scan history │   ┌──────────────────────────────────────────────────────────────────┐          │
│  └──────────────┘   │ Reference card DB (sets, numbers, variants, images) synced nightly│          │
│                     └──────────────────────────────────────────────────────────────────┘          │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐          │
│  │ DATA LAKE (the moat): consented scans → labelling → training sets → in-house models   │          │
│  └─────────────────────────────────────────────────────────────────────────────────────┘          │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
         ▲
         │  External feeds: Pokémon TCG API / Scrydex, TCGdex (catalog + Cardmarket €/TCGPlayer $ prices),
         │  later eBay Browse/sold-comps for graded valuation.
```

### 1.2 Data flow (capture → portfolio)

| Step | What happens | Where |
|---|---|---|
| 1. Capture | Guided camera locates card, runs blur/glare/framing quality gate, captures 1..N high-res stills | On-device |
| 2. Pre-filter | On-device detector crops + deskews; rejects bad frames before upload (saves bandwidth & API cost) | On-device |
| 3. Recognize | Identify set, number, language, variant (holo / reverse / 1st ed) | Recognition service |
| 4. Match | Resolve recognition output to a canonical card ID in reference DB; **variant disambiguation** via set symbol + bottom number | Backend + reference DB |
| 5. Value | Look up cached Cardmarket € (primary) / TCGPlayer $ (secondary); for graded, use sold-comps | Pricing service |
| 6. Portfolio | Append to user collection, snapshot value, update history | Postgres |
| 7. Pre-grade | If user requests, run centering CV + corner/edge/surface CNN on the high-res stills | Pre-grade service |
| 8. Anti-fake | Authenticity score (vintage/high-value focus) from texture, print pattern, holo signature | Anti-fake service |
| 9. Data capture | If consented, store images + outcomes into data lake for future training | Data lake |

Steps 3–8 run as **independent async stages** so any one can be swapped from "bought API" to "in-house model" without touching the app.

---

## 2. Recommended stack

| Layer | Choice | Justification |
|---|---|---|
| **Mobile** | **React Native (Expo + dev client)** with `react-native-vision-camera` (frame processors) + on-device ML via CoreML/TFLite | Cross-platform from one codebase = small team velocity. Vision-camera's frame processors give the real-time per-frame access needed for stack/video scanning. Flutter is a fine alternative; we pick RN for the larger JS/TS hiring pool and ML SDK maturity. **[DEP: Design]** capture UX is built on this. |
| **On-device ML runtime** | CoreML (iOS Neural Engine) / TFLite (Android) running a quantized YOLO/RF-DETR detector | YOLO11/RF-DETR class models hit 60+ FPS on iPhone Neural Engine — enough for live multi-card scanning and quality gating without a round-trip. |
| **Backend** | **Python (FastAPI)** for ML-facing services; thin **TypeScript (NestJS/Node)** edge API optional | Python keeps backend in the same language as the ML stack (PyTorch, OpenCV, numpy) — no context-switch tax for a small team. FastAPI is async, fast, OpenAPI-native. |
| **Async / queue** | **Redis (RQ/Celery)** at small scale → **SQS + workers** at medium scale | ML stages are bursty and latency-tolerant; decouple from the request path. Start simple. |
| **Primary DB** | **PostgreSQL** (Supabase or RDS) | Relational portfolio/history data, strong JSONB for card metadata, mature, cheap. Supabase bundles Auth + storage + Postgres to move fast. |
| **Cache / hot data** | **Redis** | Pricing cache, rate-limit counters, dedupe of recent scans. |
| **Object storage** | **S3** (or Supabase/Cloudflare R2) | User photos + model crops. R2 has zero egress — relevant since images are large and re-served. |
| **Auth** | **Supabase Auth or Clerk** | Offload OAuth/email/social, MFA, GDPR-friendly data export/delete primitives. |
| **Billing** | **RevenueCat** (mobile subscriptions) + **Stripe** (web) | Power-user scanning needs a subscription/quota model (see §5); RevenueCat handles App Store/Play receipt complexity. |
| **Cloud** | **AWS** primary (or GCP); EU region (`eu-central-1` / `eu-west-3`) | EU-first product → **data residency in the EU** for GDPR. Region choice is a compliance decision, not a preference. |
| **ML serving** | Containerized model servers (GPU when needed) behind the queue; managed inference (Replicate/Modal/SageMaker) for spiky GPU | Avoid running idle GPUs early; rent burst capacity until volume justifies reserved instances. |
| **Observability** | Sentry + OpenTelemetry + a metrics stack (Grafana) | Per-stage latency/cost tracking is essential for the unit economics in §5. |

---

## 3. The three AI/ML pipelines

### 3.1 Recognition + variant disambiguation

**Buy-vs-build: BUY first, build a hybrid later.**

| Aspect | Plan |
|---|---|
| Start with | **Ximilar Collectibles Recognition** (Pokémon EN/JP + Korean/Thai support, returns set/number/variant attributes, ~10 credits ≈ ~$0.01/scan) as the cloud recognizer. In parallel, deploy a **Roboflow/YOLO on-device detector** purely for *localization + quality gating + offline rough match*. |
| The hard part | **Variant disambiguation** (same art, different set ⇒ price ×10). This is *not* solved by artwork matching alone. We solve it deterministically: after recognition, **OCR/crop the bottom-corner card number + classify the set symbol**, then resolve against the reference DB. The set symbol + collector number are the ground truth; the artwork only narrows candidates. |
| Accuracy expectation | Out-of-box recognition ~90% top-1; competitors (e.g. Ludex) sit ~89%. Our disambiguation layer + a "confirm this card?" UX step (**[DEP: Design]**) should push *effective* accuracy higher by catching the ×10 variant errors specifically. **Never silently guess a high-value variant** — show top-2 candidates with price delta when confidence is low. |
| Path to proprietary | Every confirmed scan (user taps "yes, that's my card") is a **free labelled example**. After ~hundreds of thousands of consented, confirmed scans, train an in-house embedding + set-symbol classifier. Goal: move the common 80% of scans to **on-device inference at ~$0 marginal cost**, falling back to the cloud API only for low-confidence/rare cards. |
| Data strategy | Confirmed-scan loop (above) + bootstrap from reference-DB card images (~20k cards) for synthetic augmentation (rotation, glare, wear). |

### 3.2 Pre-grading

**Buy-vs-build: hybrid from day one — build centering, buy corners/edges/surface initially.**

| Sub-task | Method | Notes |
|---|---|---|
| **Centering** | **Build in-house immediately.** Classic CV: detect inner art border vs outer card edge, compute L/R and T/B ratios at pixel level. | Cheapest, most defensible, most *mathematically honest* signal. Runs on-device or cheaply server-side. This is the headline pre-grade feature. |
| **Corners / edges** | Start with **Ximilar `/v2/grade`** (centering+corners+edges+surface, overall + breakdown), supports Cardmarket/TCGPlayer/PSA-style modes. Build our own CNN as data accrues. | Corner wear has a distinct visual signature; CNNs do well here. |
| **Surface** | Buy initially; **known hard limit**: micro-scratches, print lines, vintage holo haze are often invisible without raking light. | **[DEP: Design]** must provide a **multi-angle / tilt-to-catch-glare capture flow**, or surface scoring will be unreliable and overpromise. This is the single biggest capture-UX dependency. |

- **Accuracy expectation (set honestly):** ~±1 grade in ~95% of cases; ~±0.5 in ~85–90% under good capture. Market these as **probability distributions over grades** ("likely PSA 8–9, 70% chance ≥8"), not a single number. **[DEP: Product]** owns the disclaimer that this is pre-screening, not a grade.
- **Path to proprietary moat:** the real gold is **AI prediction → actual PSA/CGC outcome pairs.** Add a "log your real grade" feature; offer an incentive. Once we have thousands of (photos → real slab grade) pairs, our model can outperform generic graders *because our training labels are ground-truth outcomes*, not other AIs' guesses.

### 3.3 Counterfeit detection

**Buy-vs-build: BUILD (mostly), because no commodity API does this well — it is a differentiator.**

| Aspect | Plan |
|---|---|
| Approach | Multi-signal authenticity score, **scoped to vintage/high-value cards** (where fakes cluster and the value justifies the effort): (1) **print-pattern / rosette analysis** at high magnification (real cards have characteristic CMYK dot patterns; fakes differ); (2) **holo/foil signature** under varying angle (**[DEP: Design]** tilt capture again); (3) **font/layout/color-profile** deviation vs reference; (4) **texture/cardstock** cues; (5) cross-check the recognized card actually *exists* in that variant/era (catches "cards" that were never printed). |
| Start with | Heuristic ensemble + a small CNN trained on a curated known-fake/known-real set. Be explicit: low recall is acceptable early; **false "fake" accusations are reputationally dangerous** — output "authenticity score / needs expert review," never a binary "FAKE." |
| Accuracy expectation | Modest at launch. Position as a **risk flag** for expensive cards, recommending professional authentication above a value threshold. |
| Data strategy | Hardest dataset to source. Partner with collectors/graders for known-fake samples; mine community-flagged counterfeits; every high-value scan that later gets a real PSA/CGC result (genuine by definition) adds a verified-genuine example. |

**Cross-cutting:** all three pipelines write `(image, model_output, user_confirmation, later_ground_truth)` to the data lake. That loop is the company's compounding asset.

---

## 4. Data sources & integrations

| Source | Use | Access reality / ToS concern |
|---|---|---|
| **Pokémon TCG API (pokemontcg.io / now Scrydex)** | Catalog (sets, numbers, variants, images) + **Cardmarket € and TCGPlayer $ price points** in one call | Self-serve, free/affordable tiers. Surfaces Cardmarket avg/trend (7/30/etc.) legally. **Primary integration.** |
| **TCGdex** | Catalog + multilingual + pricing (TCGPlayer hourly, Cardmarket daily, variant-level, 1/7/30d trends) | Self-serve, multilingual (good for JP/other languages). Use as **catalog backbone + redundancy.** |
| **Cardmarket API (direct)** | Ideal EUR primary source | **Gated:** only commercial sellers / verified 3rd-party apps; presentation of prices needs prior written agreement; v2 migration by May 2026. **Do not block MVP on this** — pursue partner status in parallel as a later upgrade. |
| **TCGPlayer API (direct)** | USD secondary | **Effectively closed to new developers since late 2024 (eBay-owned).** Don't plan around getting a key; consume via aggregators. |
| **eBay Browse / sold comps** | **Graded-card valuation** (PSA/CGC slabs trade very differently from raw) | Real eBay developer access exists; add post-MVP for graded portfolio accuracy. |
| Self-serve price aggregators (JustTCG, PokéWallet, PriceCharting, PokemonPriceTracker) | Fallback/redundancy, graded values, historical | Vet ToS per vendor; use as backup feeds to avoid single-source dependency. |

**Storage & refresh strategy:**
- Sync the **reference card DB nightly** into our Postgres (don't hit external catalog APIs on the hot path).
- **Pricing cache:** refresh **daily** for the long tail, **hourly** for high-value/high-traffic cards. Serve from Redis; persist daily snapshots to Postgres to build **our own price history** (which also de-risks any single feed disappearing).
- **Legal note for Product/Legal:** redistributing third-party prices in a commercial app — verify each provider's commercial-use and presentation terms in writing. Cardmarket explicitly restricts presenting their prices without agreement; relying on an aggregator that *holds* that right is cleaner, but confirm the aggregator's terms permit our resale/display. **[DEP: Product/Legal]**

---

## 5. Cost model & unit economics (infra/ML)

### 5.1 Per-scan cost (early, buy-heavy)

| Component | Approx cost/scan | Notes |
|---|---|---|
| Recognition (Ximilar) | ~$0.01 | ~10 credits/card |
| Pre-grade (Ximilar `/v2/grade`, when invoked) | ~$0.01–0.03 | Only when user requests grading; full grade > condition-only |
| Anti-fake (in-house) | ~$0.001–0.005 | Mostly our compute; only on high-value cards |
| Image upload + storage + bandwidth | ~$0.001–0.005 | High-res images; R2/S3 lifecycle to cold storage |
| Pricing lookup | ~$0 (cached) | Amortized aggregator subscription, not per-call |
| **Blended/scan (recognition only)** | **~$0.012–0.02** | |
| **Blended/scan (with pre-grade)** | **~$0.03–0.05** | |

### 5.2 Monthly infra estimate

| Scale | Assumptions | Rough monthly |
|---|---|---|
| **Small (MVP)** | 5k MAU, ~150k scans/mo, ~20% pre-graded | **~$2.5k–5k** (API credits dominate ~$1.5–3k; infra ~$1–2k) |
| **Medium** | 50k MAU, ~2M scans/mo, ~25% pre-graded | **~$25k–45k**, *unless* on-device + caching cut API share — then materially lower |

### 5.3 Where costs explode — and the controls

| Risk | Control |
|---|---|
| **Power users scanning unlimited stacks** (each frame → cloud API) | (a) **On-device pre-filter** so only confirmed, deduped cards hit the cloud; (b) **dedupe** identical/near-identical frames; (c) **plan quotas** — free tier limited scans/mo, paid tiers higher (RevenueCat). **[DEP: Product]** sets the quota tiers. |
| **Pre-grade on every card** | Make grading an explicit, possibly metered action — not automatic on every scan. |
| **Cloud recognition as default forever** | The strategic cost lever: migrate the common-card 80% to **in-house on-device models** so marginal recognition cost → ~$0. Cloud API becomes the rare-card fallback. This is *the* reason the data-capture loop in §3 matters financially, not just for the moat. |
| **Image bandwidth/storage** | Upload crops not full frames where possible; lifecycle policies to cold storage; R2 zero-egress. |

---

## 6. Scalability, security & privacy

- **EU-first ⇒ GDPR is a first-class constraint, not an afterthought.**
  - **EU data residency:** Postgres + image storage in EU region.
  - **Lawful basis & consent:** Camera images are personal data. **Separate, explicit, revocable consent** to use scans for *model training* — distinct from consent to use the app. No training-set inclusion without it. **[DEP: Design/Legal]** for the consent UX/copy.
  - **Data-subject rights:** export and **delete** (right to erasure) must propagate to the data lake/training sets, not just the live DB. Design data lineage so a deleted user's images can actually be purged from training corpora.
  - **Data minimization:** default to storing crops + derived features, not raw video. Don't persist live video streams.
- **Security:** mTLS/TLS in transit; encryption at rest; signed, expiring URLs for image access; per-user authz on portfolio data; secrets in a vault; least-privilege IAM on the data lake.
- **Abuse / fraud:** rate-limit + quota enforcement at the gateway (protects COGS and the APIs); bot/scrape detection; watch for users probing the valuation engine. For anti-fake specifically, **avoid defamation risk** — never publish a binary "counterfeit" verdict on a specific listing/seller; output is private "authenticity risk, seek expert review."
- **Scalability:** stateless API behind a load balancer; ML stages scale independently off the queue; GPU autoscaling via managed inference until reserved capacity is justified; pricing served from cache, never live external calls on the hot path.

---

## 7. Build plan & milestones (small team)

Assume ~4–6 engineers (2 mobile, 2 backend/infra, 1–2 ML).

| Phase | Duration | Deliverables | Riskiest unknowns / spikes |
|---|---|---|---|
| **Phase 0 — De-risk spikes** | 2–4 wks | Validate the scary stuff *before* committing | **SPIKE A:** variant-disambiguation accuracy (set symbol + bottom-number OCR/classify) — does it reliably catch ×10 errors? **SPIKE B:** real-time on-device detection FPS on mid-range Android. **SPIKE C:** confirm legal price-display path via aggregator(s). **SPIKE D:** pre-grade centering accuracy vs a few known graded cards. |
| **Phase 1 — Core scan loop** | 4–6 wks | Capture → recognize (Ximilar) → match → value (€ primary) → portfolio + history. Auth, billing scaffolding, quotas. | Reference-DB sync + pricing cache freshness; capture quality gate **[DEP: Design]**. |
| **Phase 2 — Pre-grade v1** | 4–6 wks | In-house centering + bought corners/edges/surface, shown as grade *probability*. Guided multi-angle capture. | Surface reliability under poor lighting; **[DEP: Design]** tilt/raking-light capture flow. |
| **Phase 3 — Anti-fake v1 + data loop** | 4–6 wks | Authenticity risk score for high-value cards; "log your real grade" + consent-gated data capture into the lake; labelling pipeline. | Sourcing known-fake training data; consent/erasure plumbing through the data lake. |
| **Phase 4 — Stack/video scanning** | 3–5 wks | Continuous multi-card scanning with on-device dedupe | Throughput vs accuracy tradeoff; cost control on bursty scanning. |
| **Phase 5 — Proprietary models / cost-down** | ongoing | Move common-card recognition on-device; train pre-grade on real-outcome pairs; graded valuation via eBay comps | Dataset volume to beat bought APIs; on-device model size/accuracy. |

**De-risk order rationale:** the two things that can *kill* the product are (1) getting high-value **variants wrong** (destroys trust + portfolio accuracy) and (2) having **no legal path to display prices**. Both are cheap to test and must be settled in Phase 0 before real money is spent.

---

## 8. Hard dependencies on other deliverables (summary)

| # | Dependency | Owner |
|---|---|---|
| 1 | Guided-capture UX enabling pixel-level centering + multi-angle/raking-light surface & holo capture | **Design** |
| 2 | "Confirm this card" disambiguation step + top-2 candidate display when confidence is low | **Design + Product** |
| 3 | Messaging: pre-grade = pre-screen, not a grade; anti-fake = risk flag, not a verdict | **Product** |
| 4 | Scan-quota / subscription tiers (the primary COGS control lever) | **Product** |
| 5 | Legal sign-off on price-data redistribution + training-data consent copy | **Product / Legal** |

---

### Sources

- Ximilar Collectibles Recognition & Grading docs — https://docs.ximilar.com/collectibles/recognition , https://docs.ximilar.com/collectibles/card-grading
- Cardmarket API access/terms — https://help.cardmarket.com/en/cardmarket-api , https://help.cardmarket.com/en/api-partnerships
- TCGPlayer API closed-to-new-developers context — https://tcgapi.dev/blog/tcgplayer-api-alternative/ , https://justtcg.com/blog/the-definitive-tcgplayer-api-alternative-for-developers-in-2025
- Pokémon TCG API / Scrydex (Cardmarket € + TCGPlayer $) — https://pokemontcg.io/ , https://docs.pokemontcg.io/api-reference/cards/card-object/
- TCGdex markets/prices — https://tcgdex.dev/markets-prices
- On-device YOLO/RF-DETR mobile performance — https://blog.roboflow.com/best-ios-object-detection-models/ , https://blog.roboflow.com/yolo26/
- AI grading accuracy vs PSA & surface limitations — https://www.snapgradeai.com/blog/best-ai-pokemon-card-grading-apps-2026 , https://cardgrade.io/blog/ai-vs-human-card-grading
