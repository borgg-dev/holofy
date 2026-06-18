# Audit — Spike D: Pre-grade Centering

**Auditor:** independent ML + Backend lens (adversarial)
**Date:** 2026-06-18
**Artifacts:** `spikes/centering/` (centering.py, synthetic.py, cli.py, test_centering.py, README.md, FINDINGS.md, requirements.txt)
**Charter sections applied:** §3.1 (Product/PMF, honest-framing), §3.2 (Architecture), §3.3 (Backend), §3.6 (Premium gate)

---

## Verdict

| Lens | Avg | Result |
|------|-----|--------|
| Architecture (§3.2) | 2.75 | **PASS** |
| Backend (§3.3) | 2.50 | **PASS** |
| Product / PMF (§3.1) | 2.75 | **PASS** |
| Premium gate (§3.6) | — | **PASS (conditional)** — one AI-tell found (dead code); see P1 |

The headline claim survives scrutiny. The synthetic suite is **not** circular — mutation
testing killed every injected regression. The "0px error" claim reproduces. Centering is
honestly framed as an estimate + confidence, and the confidence model correctly rates
*measurement quality* independent of *centering quality*. The perspective/skew limitation is
surfaced as the single biggest dependency, not buried.

One genuine defect (unreachable dead-code branch) and three doc/test mismatches keep this
short of a clean sweep. None are blockers for a Phase-0 spike; all are quick fixes.

---

## Did the hard scrutiny hold up?

**Is "0px error on 400 synthetic cards" real and reproducible?** Yes. Re-ran the sweep
independently at n=400 with the same RNG envelope (`integers(15,80)`, noise ≤ 6): **max
border error = 0px**. The in-suite test (`test_recovers_borders_exactly_across_a_randomised_sweep`,
test_centering.py:144) only loops **100**, while README.md:72 and FINDINGS.md:25 both claim
**400**. The claim is true but the committed test under-covers it (see P2).

**Is the synthetic test circular?** No — this was the load-bearing question and it passes.
Mutation testing on the production detector:

| Injected bug | Suite result |
|---|---|
| `_border_from` off-by-one (`+1`→`+2`) | KILLED (1 failed) |
| `_border_from` drop the `+1` | KILLED (3 failed) |
| card-edge off-by-one (`start+1`→`start`) | KILLED (1 failed) |
| `_classify` uses `min` not `max` axis | KILLED (9 failed) |
| `confidence` hard-wired to `1.0` | KILLED (1 failed) |

The generator (synthetic.py) draws geometry from chosen border widths; the detector
(centering.py) recovers them via an independent gradient-peak path with its own index
convention. They are not the same code computing the same thing, so a regression in the
index convention surfaces. The exact-recovery sweep is what makes off-by-one mutants fatal —
this is the right test design, not a green-but-toothless suite.

**Is the border-detection method sound or fragile?** Sounder than expected for a flat scan.
Independent perturbation tests on a known card:
- Gaussian-blurred borders: exact recovery at σ=1,2; correctly degrades to `CenteringError`
  at σ=4 (full-bleed-like). Gradient *peak* stays at the edge midpoint under symmetric blur.
- Textured art panel (σ=40 noise inside the art): exact recovery — mean-profile collapse
  averages out interior texture.
- Horizontal luma gradient / vignette: exact recovery — `np.diff` is shift-invariant to a
  slowly-varying background.

The method is genuinely robust to the perturbations it claims (noise, soft edges, low
contrast). Its real fragility (perspective/skew, glare, rounded corners) is explicitly
out of scope and documented — see PMF below.

**Is centering honestly framed as an estimate, not a grade?** Yes, consistently.
`CenteringResult` docstring (centering.py:92), `report()` header literally reads
"Centering estimate (pre-grade, not a grade)" (centering.py:113), `QualityBand` docstring
states it mirrors PSA tolerance *shape* "without claiming to *be* a grade" (centering.py:60-66).
Aligns with §3.1 and TECHNICAL_ARCHITECTURE.md:15.

**Does confidence model measurement quality vs centering quality correctly?** Yes — verified
empirically. With centering fixed at 50/50, confidence tracks border↔art contrast
(Δ145→1.00, Δ20→0.27, Δ≤10→`CenteringError`). With contrast fixed high, an 86/14 severely
off-center card still reads **confidence 1.00**. The dedicated test
`test_off_center_card_is_high_confidence_not_low` (test_centering.py:96) pins exactly this.
This is the correct and non-obvious behavior.

---

## Per-criterion scores

### Architecture (§3.2) — avg 2.75 → PASS
| Criterion | Score | Note |
|---|---|---|
| Fits system design; stages swappable (buy→build) | **3** | Matches TECHNICAL_ARCHITECTURE.md:120-126 "build centering immediately." Clean `CenteringResult` contract that the pre-grade service can compose with bought corners/edges/surface. Detector is internally swappable (FINDINGS notes a learned segmenter as the eventual upgrade). |
| Clear module boundaries, no leaky coupling, no premature abstraction | **3** | `centering.py` (measurement) / `synthetic.py` (fixtures) / `cli.py` (entry) cleanly separated. Pillow import is local to `load_grayscale` to keep the numpy core dependency-light. No speculative interfaces. |
| Data-capture/consent loop honored | **2** | N/A for a pure measurement spike; FINDINGS.md:56-68 correctly identifies the label-generation moat loop this feeds. No user data touched. |
| Decisions traceable | **3** | FINDINGS.md documents the buy-vs-build call, the np.diff index-convention decision, and the capture dependency. No ADR needed at spike grade. |

### Backend (§3.3) — avg 2.50 → PASS
| Criterion | Score | Note |
|---|---|---|
| Idiomatic Python; typed | **3** | Full type hints, `NDArray` aliases, frozen `slots=True` dataclasses, `Final` constants, `from __future__ import annotations`. Clean, idiomatic, not tutorial-grade. Async N/A (CPU-bound numpy). |
| Real error handling / validation / observability | **2** | Good: dimension/size checks, full-bleed and noise-floor rejection, typed `CenteringError` with specific messages; CLI maps failures to distinct exit codes (2/3). Docked one point for the **unreachable** `min_border` branch (P1) and no logging/metrics hooks (acceptable at spike grade). |
| Tests: unit + contract, green | **3** | 19 passed. Survives mutation testing (see above). Covers band thresholds, worst-axis, confidence semantics, full-bleed/too-small/wrong-shape branches, PNG round-trip. Genuinely catches regressions. |
| No secrets; data residency | **2** | No secrets, no network, no PII. N/A but clean. |

### Product / PMF (§3.1) — avg 2.75 → PASS
| Criterion | Score | Note |
|---|---|---|
| Maps to a real ICP need (valued·verified·pre-graded) | **3** | Centering is the §3.2 headline pre-grade signal; interpretable "55/45 L-R" is exactly the trust-building wedge (FINDINGS.md:60-62). |
| Honest framing (ranges + confidence, never absolute) | **3** | Estimate-not-grade stated in code output, docstrings, README, FINDINGS. Confidence is first-class. Coarse bands, not a fake numeric grade. |
| Freemium/quota boundary | **2** | N/A for spike; no scope violation. |
| No scope creep beyond MVP | **3** | Tightly scoped to measurement. Perspective/glare/rounded-corners explicitly deferred to capture stage (README.md:77-83, FINDINGS.md:33-54). The "looks precise but is wrong on unrectified input" failure mode is named as the most dangerous one (FINDINGS.md:73-77) — exactly the honesty §3.1 demands. |

### Premium gate (§3.6) — PASS (conditional)
Code reads as a thoughtful engineer's work, not AI sludge: domain-precise naming, restraint,
calibration constants with *why* not *what* comments, no `handleData`/`temp`/`foo`. House
style is consistent across all four files. **One AI-tell** prevents a clean pass: a
provably-unreachable defensive branch with a never-firable error message and an
effectively-dead constant (P1). Resolve P1 and this is an unconditional Premium PASS.

---

## Prioritized findings

### P1 — Unreachable dead-code branch + effectively-dead constant (Premium AI-tell)
`centering.py:213,224-225` and `:41`.
`min_border = max(guard, int(span * _MIN_BORDER_FRACTION))` with `_MIN_BORDER_FRACTION=0.01`
is always ≤ `_EDGE_GUARD_FRACTION=0.02`, so `min_border == guard` for every span. But
`_border_from` (centering.py:240) always returns `guard + peak + 1 ≥ guard + 1 > min_border`.
Proven across spans 50–1000: the `if near < min_border or far < min_border:` reject at
line 224 **can never fire**, and its `CenteringError("inner border not separable…")` is
unreachable. `_MIN_BORDER_FRACTION` exists only to feed this dead branch.
*Fix:* delete the branch + constant, or make the guard actually meaningful (e.g. base
`min_border` on a fraction that can exceed `guard`, or floor `_border_from` differently). As
written it is exactly the "speculative/dead code" §3.6 auto-FAIL pattern.

### P2 — In-suite sweep loops 100; docs claim 400 (test/claim mismatch)
`test_centering.py:148` loops `range(100)`; README.md:72 and FINDINGS.md:25 both headline
**400 cards**. The 400 claim reproduces independently, but the *committed* regression guard
is 100. Either bump the loop to 400 or correct both docs to 100 so the suite proves the
claim it ships.

### P3 — README claims "19 passed" while FINDINGS frames the suite size loosely
`README.md:67` says `# 19 passed` (correct, verified). FINDINGS.md prose ("recovers every
border width exactly") is fine, but cross-doc the card counts (P2) so a reader isn't told
two different numbers. Minor.

### P4 — `np.gradient`-bias lesson not reproducible on the cited centered case
FINDINGS.md:28-31 claims switching from `np.gradient` to `np.diff` "removed a systematic
1-px asymmetry." On a perfectly-centered synthetic card both methods returned equal
borders (40/40) in my check, so the specific reproduction is weaker than stated. The
*general* index-convention point is valid and the shipped `np.diff` convention is correct
and well-documented (centering.py:180-196, :231-240); just soften the claim or cite the
asymmetric case where it actually manifests. Low priority — does not affect correctness.

### P5 — Confidence saturation/floor constants are reasonable but uncalibrated against real data
`_MIN_TRANSITION_LUMA=12`, `_CONFIDENT_TRANSITION_LUMA=60` (centering.py:46,50) are sensibly
chosen and honestly commented as tuned to capture noise, but no real-card validation exists
yet (none expected at spike grade). Flag for Phase-2 calibration against the guided-capture
output. Informational.

---

## Bottom line

Spike D answers its Phase-0 question convincingly: in-house, OpenCV-free, dataset-free
centering is cheap, accurate on aligned input, honestly framed, and — critically — covered
by a suite that actually catches regressions rather than rubber-stamping them. The single
real defect is a dead-code branch (P1); the rest are doc/test hygiene. Fix P1 and P2 and
this is a clean PASS on every lens including Premium.

---

## Refine & gate resolution (orchestrator, 2026-06-18)
P1 (the §3.6 AI-tell) fixed: the unreachable `min_border` branch, its local, and the dead `_MIN_BORDER_FRACTION` constant removed — the `guard` floor already enforces the minimum, so the check was genuinely redundant. P2 fixed: the randomised sweep now loops 400 (matching README/FINDINGS); re-run confirms `19 passed` with max border error 0px at n=400. **Premium gate: PASS (unconditional).**
