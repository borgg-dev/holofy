# Holofy — Development Charter & Autonomous Build Loop

**Purpose:** Define how Holofy is built — autonomously, iteratively, and to a premium bar — from scratch to shippable product. This document governs every work cycle. The builder and auditor agents are bound by it.

**Prime directive:** *Ship a genuinely premium product that looks and reads as though a top-tier product studio built it — never like AI-generated output.* This bar overrides "it works." Working-but-generic = FAIL.

---

## 1. The Build–Audit Loop (every work unit obeys this)

A **work unit** = one vertical slice (a feature, component, service, or spike) small enough to build and audit in one cycle.

```
PLAN → BUILD → AUDIT → GATE → (REFINE ↺ | MERGE ✓)
```

1. **PLAN** — Define the slice, its Definition of Done (§4), and which rubrics apply.
2. **BUILD** — A domain **builder agent** implements it to the standards in §3.
3. **AUDIT** — An **independent auditor agent** (never the builder) scores it against the relevant rubric(s) in §3. Output: per-criterion score + PASS/FAIL + specific, actionable findings.
4. **GATE** —
   - **PASS** (meets bar on every criterion, Premium gate included) → commit, mark task done.
   - **FAIL** → REFINE: feed findings back to the builder, rebuild, re-audit. Loop.
5. **ESCALATE** only on a true blocker (§5) or after **3 failed refine cycles** on the same unit (signals a planning/spec problem, not an execution one).

**Cross-cutting audits** run at every phase boundary (not just per-slice): architecture coherence, design-system consistency, PMF alignment, security posture. Drift caught here spawns refine tasks.

---

## 2. Roles (who does what)

| Role | Responsibility |
|------|----------------|
| **Orchestrator** (me) | Owns the backlog, sequences work, spawns builders/auditors, runs the gate, persists state, escalates only per §5. |
| **Builder agents** | Domain specialists: `frontend`, `backend`, `ml`, `infra`. Implement slices to §3 standards. |
| **Auditor agents** | Adversarial reviewers, one per lens: `product/pmf`, `architecture`, `backend`, `design`, `security`. Independent of the builder. Score, don't fix. |
| **Premium gatekeeper** | A dedicated final auditor that applies §3.6 only. Has veto power. |

Builder and auditor for the same slice are **always distinct agents** spawned fresh, so the audit is a true second opinion.

---

## 3. Quality rubrics (the bar)

Each criterion is scored **0–3** (0 absent · 1 weak · 2 solid · 3 excellent). **A slice passes a lens only if every criterion ≥ 2 and the lens average ≥ 2.5.** The Premium gate (§3.6) requires **every criterion ≥ 2 AND zero "AI-tells".**

### 3.1 Product / PMF
- Slice maps to a real ICP need in the master plan (valued · verified · pre-graded).
- Honest framing of pre-grade/anti-fake (ranges + confidence, never absolute claims).
- Freemium/quota boundary respected where relevant.
- No scope creep beyond the market-fit MVP.

### 3.2 Architecture
- Fits the documented system design; ML stages remain swappable (buy→build).
- Clear module boundaries, no leaky coupling, no premature abstraction.
- Data-capture/consent loop honored where user content is involved (the moat).
- Decisions traceable to an ADR when non-obvious.

### 3.3 Backend
- Idiomatic FastAPI/Python; typed; async where it matters.
- Real error handling, validation, and observability — not happy-path only.
- Tests: unit for logic, integration for the slice's contract. Green.
- No secrets in code; EU data-residency & GDPR primitives respected.

### 3.4 Frontend / Design
- **Bespoke** — built on Holofy design tokens, zero default-framework chrome visible.
- Custom components, not stock-library look; matches the Foil Vault system.
- Intentional motion/micro-interactions on signature moments; respects `prefers-reduced-motion`.
- Real empty / loading / error / offline states. Pixel & optical alignment. Accessibility (contrast AA, screen-reader labels, 44pt targets, locale number/currency formatting).

### 3.5 Security & Privacy
- Authz on every user-data path; signed expiring URLs for images.
- Explicit, revocable consent for training-data use; erasure propagates to the data lake.
- Rate-limit/quota enforced (protects COGS + APIs).
- Anti-fake output never a binary public "FAKE" verdict (defamation risk).

### 3.6 Premium / Not-Generic gate (overrides all — the founder's #1 demand)
**PASS requires the answer to "would a top-tier studio ship this?" to be an honest yes.** Auto-FAIL on any of these **AI-tells**:
- Generic/stock visual look; default component-library styling; centered-everything layouts; lorem-ipsum or placeholder copy left in.
- Over-commenting that narrates the obvious; comments explaining *what* not *why*.
- Speculative abstraction, dead code, unused params, `handleData`/`foo`/`temp` naming, copy-paste drift.
- Boilerplate README/marketing voice; em-dash-soup hype copy; emoji-as-decoration in product UI.
- Inconsistent house style across files; mixed conventions; "tutorial-grade" code.
- Missing the unglamorous polish: focus states, transitions, error microcopy, edge cases.
**Positive bar:** a coherent house style, domain-precise naming, restraint, taste, and the unglamorous details done right.

---

## 4. Definition of Done

**Per slice:** builds clean · tests green · passes all applicable lens audits · passes Premium gate · committed with a real message · task marked done · any follow-ups filed.

**Per phase:** all slices done · cross-cutting audits pass · demo path works end-to-end · phase retro filed (what passed/failed audit, rubric tweaks) · `STATUS.md` updated.

**Product (final):** all phases done · KPIs instrumented · legal gate cleared · store-submission-ready build · no open Premium-gate failures.

---

## 5. Autonomy contract (so you are NOT pinged constantly)

**I decide and proceed autonomously on:** all technical/design/product-execution choices within the master plan and this charter, library selection, code structure, copy, the build/audit/refine loop, sequencing, and refactors.

**I escalate to you ONLY when genuinely blocked — batched, never one-at-a-time:**
1. **Money / accounts** — anything needing your credentials or spend: Ximilar key, price-aggregator subscription, Apple ($99/yr) & Google ($25) developer accounts, AWS/cloud billing, domain.
2. **Legal sign-off** — the brand-name/IP review and price-data redistribution terms (hard launch gates).
3. **Irreversible / outward-facing** — publishing, real-money charges, anything public under the brand.
4. **A genuine plan-level fork** — only if a Phase-0 finding invalidates a core assumption (e.g., no legal price path exists).

Everything else: I build it, audit it, and keep moving. Blockers accumulate in `BLOCKERS.md`; I surface them at phase boundaries or when one actually halts progress — not as a stream of questions.

**Until those external dependencies are provided, I build everything that doesn't require them** (full app against mocked/stubbed external services, complete design system, all UI, business logic, tests), so the moment you supply keys/accounts we integrate and ship.

---

## 6. State & persistence (survives context resets)

- `DEVELOPMENT_CHARTER.md` — this file (the rules).
- `STATUS.md` — current phase, what's done, what's in flight, last audit results. Updated every cycle.
- `BLOCKERS.md` — the batched escalation queue for you.
- `docs/adr/` — architecture decision records.
- `docs/audits/` — every audit report (traceability of the loop).
- Task backlog (task tool) + project memory — the durable plan-of-record.

Anyone (including a fresh me after a context reset) can resume by reading `STATUS.md` + this charter + the backlog.
