# Holofy — Production / Sellability Backlog

Consolidated from three independent specialist audits (mobile, backend/security, product/sellability) on 2026-06-19. This is the complete list of what stands between today's working MVP and a *sellable, production-ready* product. Nothing here is hidden.

Two piles: **Pile A** = code I can build and verify. **Pile B** = needs the founder's external accounts, money, or legal sign-off (I scaffold the code so it activates with a key/config, but cannot complete it alone).

---

## Pile A — code (I build & verify)

### Wave 1 — Make features real & app testable
- [x] **Real camera capture for pre-grade** — was sending mock refs the backend 404s. *(done, fa2ea6a)*
- [x] **Real camera capture for authenticity** — same. *(done, fa2ea6a)*
- [ ] **Real camera capture for rapid/stack** — per-flip capture+upload; live per-flip preview becomes "reading at review" (no on-device recognizer yet).
- [ ] **Auth reachable in the app** — add `EXPO_PUBLIC_API_URL` config + a `make mobile-watch-live` target + docs; nothing sets it today, so sign-in/up/delete are unreachable in the mode the founder runs.
- [ ] **Real account screen** — remove placeholder copy ("Collector", "sign-in arrives in next build", dead "Upgrade to Collector+"); show the real email + working sign-out/delete.
- [ ] **Camera-permission-denied UX** — explicit "enable camera / Open Settings" state instead of silently faking a capture.
- [ ] **Implement or remove stubbed result actions** — pre-grade `onLogGrade`/`onWhatAffects`, authenticity `onAuthenticate` are no-ops.
- [ ] **CardDetail / Reveal error handling** — distinguish network error from "card missing"; surface add-to-vault failures instead of swallowing them.

### Wave 2 — Security & GDPR backend hardening
- [ ] **Consent *withdrawal* purges the training lake** (GDPR Art. 7(3)) — today only account deletion purges; revoke leaves data in the lake. *(real bug)*
- [ ] **Brute-force protection on `/auth/login` & `/auth/register`** — short-window per-IP + per-email limiter (the existing one is daily).
- [ ] **Session token subject = immutable user id**, not email — prevents takeover when a deleted email is re-registered.
- [ ] **Capture ownership binding** — bind capture refs to the uploading user; verify ownership on load (IDOR defense-in-depth).
- [ ] **Request body size cap + image magic-byte validation** on `/captures` (DoS / spoofed content-type).
- [ ] **`/health` readiness** — actually ping DB (and Redis when configured) instead of always "ok".
- [ ] **TCGdex resilience** — wrap catalog HTTP errors as typed upstream-unavailable; add bounded retries + a cache so an outage degrades instead of 500-ing every scan.
- [ ] **Config validators** — require `database_url`, `datalake_sink`, `capture_storage`, `cors_allow_origins` (and a real secret) outside `local`, so a prod deploy can't silently run on SQLite / the mock lake.
- [ ] **Session logout / revocation** — a way to invalidate a token (token-version on the user); shorten TTL.
- [ ] **Graceful Redis-down behaviour** — decide fail-open vs fail-closed on the quota path.

### Wave 3 — Monetization (the "sellable" core)
- [ ] **Plan / entitlement model** on `User` (free vs paid) + a real entitlement check.
- [ ] **Premium gating** — separate pre-grade / authenticity / unlimited-scans from the free quota so paid features are actually paid.
- [ ] **Subscription backend** — Stripe (web) + RevenueCat (IAP) webhook → set entitlement. *(code; activation needs Pile B accounts)*
- [ ] **Mobile paywall + upgrade flow** replacing the dead "Upgrade" text.

### Wave 4 — Account lifecycle
- [ ] **Password reset + email verification** — needs a pluggable email sender (console backend for dev; real provider via config — Pile B).
- [ ] **Change email / change password** while logged in.

### Wave 5 — Cloud & infra (code)
- [ ] **S3/GCS object-storage adapter** behind the existing `CaptureStorage` seam *(activation needs a bucket — Pile B)*.
- [ ] **Persistent (real) data-lake writer** behind the `DataLakeSink` seam.
- [ ] **docker-compose verification** + migrations-as-separate-step, worker count, proxy headers.

### Wave 6 — Store / legal / observability (code-side)
- [ ] **App icons + splash assets** (referenced in `app.config.ts` but the files don't exist → build can't submit).
- [ ] **Onboarding flow** for first-run.
- [ ] **Analytics + crash reporting** scaffold (Sentry + PostHog), activated by DSN *(keys — Pile B)*.
- [ ] **Support contact + age gating** in-app.
- [ ] **Terms of Service + Privacy Policy** screens wired to documents *(the documents themselves — Pile B/legal)*.

---

## Pile B — needs the founder (accounts / money / legal / device)

1. **Stripe + RevenueCat accounts** (+ App Store / Play merchant setup) — to actually charge money.
2. **Apple Developer ($99/yr) + Google Play ($25) accounts** — to ship to stores.
3. **A cloud host + EU object-storage bucket + managed Postgres/Redis** — to run it for real.
4. **An email provider** (Resend/SES/Postmark) + a sending domain — for password reset / verification.
5. **Legal sign-off on commercial display/redistribution of card price data** (Cardmarket via TCGdex) — the core € feature's legal right. Possibly a paid data licence (e.g. Scrydex).
6. **Terms of Service + Privacy Policy documents** — from a lawyer (I can provide drafts/templates, not legal advice).
7. **Trademark / brand clearance** for "Holofy" in a Pokémon-adjacent space.
8. **Real-device OCR validation** — scan real Pokémon cards on a physical phone; the core promise is unproven on real photos.
9. **App Store / Play listing** — screenshots, descriptions, privacy nutrition labels / Data Safety form, age rating.

---

## Status
Pile A is being executed wave by wave, each committed and verified. Pile B items are flagged in code where they gate activation (a missing key disables the feature cleanly rather than faking it).
