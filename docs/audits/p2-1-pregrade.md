# Audit — P2.1 Pre-Grade Service

**Artifact:** `apps/api/` pre-grade slice — in-house centering, bought corners/edges/surface behind a `GradingProvider` seam, composed into an honest grade *probability range*.
**Auditor lenses:** Product/PMF (§3.1, honest-framing), Architecture (§3.2), Backend (§3.3), Premium gate (§3.6).
**Date:** 2026-06-18
**Verdict: PASS on all four lenses. Premium gate: PASS.**

## Build / test verification (ran, did not trust the report)

- `pytest -q` → **99 passed** (builder's claim confirmed).
- Centering/grading/pregrade subset → 39 passed.
- `alembic check` → the builder's invocation path is wrong (`.deps/bin/alembic` does not exist; alembic ships no console script in `.deps`, and there is no `python` on PATH). Reproduced correctly via `python3 -m alembic upgrade head && python3 -m alembic check` against a fresh SQLite target: migration `cb5a72db0ff5 → c42e26561d8c` applies cleanly and **`check` reports "No new upgrade operations detected"** — i.e. no model/migration drift. The conclusion holds; only the documented command is stale. (F4, low.)
- Independent falsification probes (range coherence sweep, worst-axis gating, false-precision attempts) all pass — see below.

---

## Lens 1 — Product / PMF (§3.1, honest-framing)

| Criterion | Score | Notes |
|---|---|---|
| Maps to real ICP need (pre-graded wedge) | 3 | Centering is the interpretable, in-house headline signal; output is the number a collector actually decides on (`p_at_least` = "P it's a 9+, worth the fee"). |
| **Honest framing — ranges + confidence, never absolute** | 3 | See hard verification below. Structurally enforced in types, DB columns, and tests. |
| Freemium/quota boundary respected | 3 | `/pregrade` charges the shared `scan:{user_id}` budget *before* any grading cost — can't sidestep the scan quota via the other endpoint. |
| No scope creep beyond MVP | 3 | Single-frame capture; bought axes mocked; nothing speculative shipped. |

**Avg 3.0 — PASS.**

### Honest-framing — hard verification (tried to falsify)

- **No absolute-grade field anywhere.** Grepped schema, model, repo, service, API: there is no `grade` / `final_grade` / `overall_grade` column or DTO field. The headline type is `GradeProbabilityRange{likely_low, likely_high, at_least, p_at_least}` with an intentional comment "There is intentionally no `grade` field" (`schemas/grading.py:75`), mirrored at the column level (`models/pregrade.py:80-86`) and asserted in tests (`test_pregrade_service.py:88`, `test_pregrade_api.py:44`).
- **Worst-axis gating genuinely prevents one bad axis reading high.** Probe: corners=10, edges=10, centering=pristine, **surface=1 @ conf 0.99** → range collapsed to **3–4**, not high (`_WORST_AXIS_WEIGHT=0.7` blends toward the minimum). Confirmed independently of the test fixture. (`services/pregrade.py:133-135`.)
- **Poor / low-confidence capture widens the band and lowers confidence — or refuses.** Probe: identical 9/9/9 scores at conf 0.41 → band widened to 7–10 (width 3) at confidence 0.41; at conf 0.9 the band tightens. Overall confidence is gated by the *least* certain axis (`min(confidences)`, `services/pregrade.py:139`), verified by sweep.
- **Refuse over guess.** Two distinct refuse paths, both returning `RETAKE` (not a confident wrong range): centering unmeasurable (`CenteringError` → full-bleed / too-small reasons) and centering below the confidence floor (`min_centering_confidence=0.4`). The low-contrast washed-out card (`card_value=140, art_value=120`) correctly refuses (`test_pregrade_service.py:161`).
- **Could not construct false precision.** Full 5⁴×5 sweep of (centering, corners, edges, surface) scores × confidences: `likely_low ≤ likely_high` always, `at_least` never exceeds `likely_high`, `p_at_least ∈ [0,1]` always — zero incoherent payloads. A perfect synthetic gem reports `p_at_least=0.5` at grade 10 (never a 100%-certain claim on a non-degenerate spread). The `PREGRADE_DISCLAIMER` is a non-optional default present on **every** response, including `retake`.

This is the strongest part of the slice — the honesty rule is encoded in the type system and the DB schema, not in copy that could rot.

---

## Lens 2 — Architecture (§3.2)

| Criterion | Score | Notes |
|---|---|---|
| Fits documented design; ML stages swappable (buy→build) | 3 | `GradingProvider` Protocol mirrors `RecognitionProvider`/`PricingProvider` exactly; real Ximilar `/v2/grade` drops in behind the same signature. |
| Module boundaries / no leaky coupling / no premature abstraction | 3 | Centering is in-house in `app/grading/`, **not** routed through the bought-axes seam (`base.py:9-11`, factory `build_grading_provider` docstring states it explicitly). Service composes; endpoint persists; repo owns SQL. |
| Data-capture/consent loop honored (the moat) | 3 | Every pre-grade persisted with sub-scores as a JSON training row alongside the eventual real grade (`models/pregrade.py` docstring, the §3.2 moat loop). `capture_ref` stored, never bytes (data minimization). |
| Traceable to design / ADR | 2 | Centering promotion is faithful to Spike D FINDINGS; the Ximilar provider swap is called out as "ADR-tracked later" but no ADR file exists yet for the grading seam. Minor. |

**Avg 2.75 — PASS.**

- **Centering promotion is faithful.** The numpy core is byte-identical to `spikes/centering/centering.py` (same `_PERFECT_TOLERANCE`, `_EDGE_GUARD_FRACTION`, `_MIN_TRANSITION_LUMA`, `_CONFIDENT_TRANSITION_LUMA`; same `np.diff` index convention that the spike's FINDINGS calls out as the core bias-fix lesson). Synthetic ratios still exact: 48/32px→60/40, 72/12px→86/14, 40/40→50/50, all at the expected bands/confidence. Only the entry point changed (accepts raw bytes → Pillow luminance decode), which is the correct production adaptation.
- **Perspective/skew limitation is NOT silently dropped.** Preserved in the production docstring (`centering.py:121-124`): "Perspective/skew on the input corrupts the ratio in a way that *looks* precise, so the capture stage owns deskew/glare gating before this runs." This is the single most dangerous failure mode for an honesty-led product and it is explicitly retained.

---

## Lens 3 — Backend (§3.3)

| Criterion | Score | Notes |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | Protocol-typed deps, frozen Pydantic models, `StrEnum`, async provider/store/repo. Clean house style consistent with scan/pricing modules. |
| Real error handling / validation / typed status codes | 3 | Refuse = typed **200** body; unresolvable capture = typed **404** (`capture_not_found`); blank ref = **422**; missing auth = **401**. No 500s on the expected failure paths — verified by tests + by probe (undecodable bytes → `RETAKE`, not a crash). |
| Tests: unit + integration, green | 3 | Unit (composition math, refuse paths, worst-axis, confidence gating) + integration (auth, estimate, retake-not-500, 404, 422, persistence). 99 green. |
| No secrets; EU residency / GDPR primitives | 3 | No secrets in code; `capture_ref` only, never bytes; `card_id` FK is `SET NULL` so history survives catalog retirement; check constraints (`band_not_inverted`, unit-interval on confidence/`p_at_least`) enforce honesty at the row. |

**Avg 3.0 — PASS.**

- SQL stays in repositories — grepped `select(`/`.execute(`/`session.get(` in `api/pregrade.py` and `services/pregrade.py`: none. The endpoint's `_resolve_card_id` goes through `CardRepository`.
- Migration `downgrade()` correctly drops indexes then the table; `down_revision` chains to the initial schema; `render_as_batch` makes it Postgres-and-SQLite safe.
- Quota charged before grading cost (COGS protection), consistent with the scan endpoint.

---

## §3.6 Premium / Not-Generic gate

**Verdict: PASS — zero AI-tells found.**

Checked for: over-commenting, speculative abstraction, dead code, generic naming, house-style drift, copy-paste drift.

- **Comments explain *why*, not *what*.** The `_WORST_AXIS_WEIGHT`, `_SPREAD_AT_*`, and band-tolerance comments justify the modelling choice (why 0.7, why a soft minimum, why these PSA tolerances) — domain reasoning, not narration. Module docstrings are precise and load-bearing.
- **Naming is domain-precise:** `GradeProbabilityRange`, `worst_offset`, `_locate_inner_border`, `_centering_retake_reason`. No `handleData`/`foo`/`temp`.
- **No dead code on inspection.** `worst_offset` and `Ratio.offset` initially read as unused in production, but both are exercised by `test_centering.py:39` — they are tested API surface, not dead. The spike-only `report()` and `load_grayscale()` were correctly **dropped** from the production module.
- **No speculative abstraction.** `image_count` is hardcoded to 1 at the endpoint, but the Protocol field is justified (the bought provider reasons about multi-angle capture for surface/holo) — forward design with a stated rationale, not a guess.
- **House style is coherent** across schema/service/centering/endpoint/repo/migration and matches the existing scan/pricing modules.
- Restraint and the unglamorous details are present: typed error envelopes, check constraints, the retake disclaimer on every response, the preserved skew caveat.

A top-tier studio would ship this.

---

## Prioritized findings

| # | Sev | Finding | Location |
|---|---|---|---|
| F1 | Low | `alembic check` command in the task brief is wrong — `.deps/bin/alembic` doesn't exist and there's no `python` on PATH. Correct invocation: `python3 -m alembic ...`. The *result* (no drift) is confirmed; only the doc'd command is stale. | task brief / dev docs |
| F2 | Low | No ADR file yet for the `GradingProvider` seam, though the code says "ADR-tracked later." File one before the real Ximilar swap so the buy→build decision is traceable per §3.2. | `docs/adr/` (missing) |
| F3 | Info | `_GradingCaptureRef(image_count=1)` is hardcoded; mock store renders a single frame. Fine for MVP, but multi-angle is the path that lets surface/holo claim more — track as a follow-up when guided multi-angle capture lands. | `api/pregrade.py:89` |
| F4 | Info | Centering accuracy is only validated on synthetic, axis-aligned input. Per Spike D FINDINGS the real-world correctness hinges on the capture-stage deskew/glare gate (the hard [DEP: Design]). Not a defect in this slice — it's correctly out of scope and documented — but it is the gating prerequisite before centering is exposed to users. | `centering.py:121-124`, FINDINGS.md |

No high or medium findings. No blocking issues.

---

## Gate decision

- Product/PMF: **PASS** (3.0)
- Architecture: **PASS** (2.75)
- Backend: **PASS** (3.0)
- Premium gate: **PASS** (zero AI-tells)

**Overall: PASS.** Recommend MERGE. File F2 (ADR) and F3/F4 (follow-ups) into the backlog; F1 is a one-line doc fix.

---
## Gate resolution (orchestrator, 2026-06-18)
PASS on all four lenses + Premium gate. Honest-framing independently verified by adversarial sweep (no false precision constructible; refuse-on-bad-capture and worst-axis gating both hold). F1 (stale alembic command) is a non-issue — apps/api/README.md already documents `python3 -m alembic ...` correctly; the auditor's constructed `.deps/bin/alembic` simply doesn't exist. F2 (grading-seam ADR), F3 (hardcoded image_count=1), F4 (deskew capture dependency note) filed to task #11. **GATE: PASS — merged.**
