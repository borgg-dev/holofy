# Holofy — Blockers (what only the founder can provide)

The autonomous mock-first build is **finished**: every feature is built, the backend runs live
(`make api-smoke`), the mobile app builds reproducibly (android + web, `make mobile-watch`), and
the productionization scaffold (Docker/compose/CI) is authored. Everything below is what flips the
product from **mock-first / dev-mode** to **real / launchable**. None is a code rewrite — each is a
key, an account, a decision, or a sign-off that activates a seam already built and waiting.

Legend: 🔑 key/secret · 💳 paid account · 🧭 decision · ⚖️ legal · ☁️ infra

---

## 1. Make the "intelligence" real (today it's mock fixtures)
| # | Blocker | Unlocks | Where it plugs in |
|---|---------|---------|-------------------|
| 1 | 🔑💳 **Ximilar API token** | Real card **recognition** + **AI grading** (replaces mock fixtures) | `RecognitionProvider` / `GradingProvider` seams (`app/providers/recognition`, `/grading`). Set `HOLOFY_RECOGNITION_PROVIDER=ximilar` + token. Also needs #6 (real capture image storage) to feed it images. |
| 2 | 🔑💳 **Pricing source** — Scrydex commercial tier (or confirm TCGdex commercial use) | Real € prices at scale (the keyless TCGdex provider already works for dev) | `PricingProvider` seam. `HOLOFY_PRICING_PROVIDER=tcgdex` works now; a paid tier + caching for volume. |
| — | (Anti-fake real CV model) | Real authenticity signals | `AuthenticityProvider` seam — this is **our** model to build later (data-loop is the moat); no external key, but needs the dataset to accrue. |

## 2. Accounts to ship & run
| # | Blocker | Unlocks |
|---|---------|---------|
| 3 | 💳 **Apple Developer** ($99/yr) + **Google Play** ($25 once) | TestFlight / store builds of the mobile app |
| 4 | 🧭🔑 **Auth provider choice** (Clerk vs Supabase vs Auth0) + keys | Real user login (replaces the HMAC dev-token seam `AuthProvider`) |
| 5 | 🧭🔑 **Billing provider** (RevenueCat + Stripe) + keys | The €5.99/mo subscription + pre-grade credits (freemium quota is already enforced) |
| 6 | ☁️💳 **Cloud account** (AWS, **EU region** for GDPR) | Real Postgres + Redis + **object storage for capture images** (the compose stack runs locally now; this is the hosted version). Capture storage is the missing piece recognition/grading need. |
| 7 | 💳 **Domain** (holofy.app / .com — verify availability) | Public URL, store listing, email |

## 3. Legal — hard launch gates (can't ship without these)
| # | Blocker | Why it's a gate |
|---|---------|-----------------|
| 8 | ⚖️ **Brand + IP review** — "Holofy" cleared (EUIPO classes 9/42), the tool-not-reseller posture + disclaimers sound, no Pokémon/Nintendo trade-dress issues | The whole product is Pokémon-adjacent; TPC/Nintendo enforce aggressively. (We've kept all Pokémon IP out of our assets/mock data by design — this confirms it.) |
| 9 | ⚖️ **Price-display redistribution terms** — written confirmation we may display Cardmarket-sourced € prices commercially (from Scrydex, or a legal opinion that aggregator-sourced display is defensible) | The € valuation feature — our core wedge — legally depends on this. Proven technically in Spike A; the *legal* right is unconfirmed. |

---

## What I can keep doing WITHOUT any of the above
Non-blocking polish (`tasks #6, #11`), more tests, design refinement, docs — and once you hand over
any item above, wiring it in is a config/seam change I can do and verify quickly. The CI
(`.github/workflows/ci.yml`) already exercises the real Postgres + Redis paths and renders app
screenshots on every push, so the parts I can't run in this sandbox get verified there.

## Resolved
- Price-data **technical** path (Spike A — proven, keyless via TCGdex).
- Mobile build (was broken — gitignored fonts; fixed + verified reproducibly).
