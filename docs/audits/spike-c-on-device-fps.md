# Audit — Spike C: on-device detection FPS

- **Work unit:** Spike C (Phase-0 SPIKE B in the architecture doc — real-time on-device detection FPS on mid-range Android)
- **Auditor:** Independent auditor agent — Architecture + ML lenses (+ Product/PMF context, Premium gate)
- **Date:** 2026-06-18
- **Artifacts:** `docs/adr/0003-on-device-detection.md`; `spikes/on_device_fps/{fps_budget.py,test_fps_budget.py,FINDINGS.md}`
- **Charter:** `DEVELOPMENT_CHARTER.md` §3.1, §3.2, §3.3 (helper script only), §3.6

## Method

Inspected all three artifacts plus `TECHNICAL_ARCHITECTURE.md` §2/§3.1/§5.3/§7 and `docs/MASTER_PLAN.md`. Ran the test suite live and independently re-derived every numeric table in the ADR and FINDINGS from the model.

`python3 -m pytest -q` → **10 passed in 0.01s.**

Re-derived ADR/FINDINGS tables directly from `fps_budget.py`:

| Claim (ADR/FINDINGS) | Re-derived from model | Match |
|---|---|---|
| iPhone NE 12 ms → ~83 raw, 30 capped, fits 33 | total=12, raw=83.3, preview=30, fits=True | ✓ |
| Flagship NPU 13 ms → ~77 raw, 30 capped | total=13, raw=76.9, preview=30 | ✓ |
| Mid GPU 32 ms → ~31 raw, ~30 capped, "borderline-yes" | total=32, raw=31.2, fits=True (≤33.33) | ✓ |
| Mid CPU 58 ms → ~17, no | raw=17.2, fits=False | ✓ |
| Low CPU 100 ms → ~10, no | raw=10.0, fits=False | ✓ |
| Dwell 400/600/800/1200 → req 10.7/7.1/5.4/3.6 FPS | 10.71/7.14/5.36/3.57 | ✓ |
| 8 FPS stack: 600ms→100 cpm, 800ms→75 cpm | can_confirm true, 100.0 / 75.0 cpm | ✓ |

The arithmetic spine is real, reproducible, and falsifiable. Nothing in the tables is hand-typed away from what the code produces.

**One internal-consistency point, in the builder's favour.** The "~75–100 cards/min" headline maps to the 600–800 ms dwell band, not to the fast (400 ms) fan: at 400 ms / 8 FPS the model yields 2.24 confirmable frames (< 3 required) → `can_confirm()` false → 0 cpm. This is *not* a contradiction — the ADR's own dwell table shows 400 ms needs 10.7 FPS, and the decision text explicitly couples the 8 FPS path to a "coach, don't drop" UI that slows an over-fast operator. The throughput claim is correctly scoped to the dwell band it names. Honest.

---

## Lens: Architecture (§3.2)

| Criterion | Score | Notes |
|---|---|---|
| Fits documented design; ML stages swappable (buy→build) | 3 | Maps cleanly to `TECHNICAL_ARCHITECTURE.md` §1.2 steps 1–2 (detect/deskew/gate on-device) and §5.3 (COGS lever). The on-device↔cloud seam is stated as load-bearing and kept clean: "swapping the cloud recognizer (Ximilar→in-house) never touches the detector, and vice-versa." The detector is deliberately single-class localisation only — naming stays in the cloud (the data-loop moat). Swap seam explicit. |
| Clear boundaries, no leaky coupling / premature abstraction | 3 | The spike is one estimation module: two dataclasses, four free functions, closed-form arithmetic, no speculative framework. The tier ladder and NNAPI-probe are described as *design*, not built in the spike — right altitude for a throwaway. No premature abstraction. |
| Data-capture/consent loop honored where relevant | 2 | Not a user-content storage path (estimation tool). But the spike correctly preserves the moat boundary: on-device dedupe (perceptual hash / tiny embedding) suppresses near-duplicates *before any upload*, and "only upload a deskewed crop of a frame that passed the gate" — which is exactly the §5.3 / data-lake discipline. Honored to the extent the slice touches it. |
| Decisions traceable to an ADR | 3 | ADR 0003 is well-formed: status (the honest "Proposed — floor-FPS-pending"), deciders, relates-to links, context, evidence, decision, a real Consequences section that names the knife-edge as the load-bearing risk, and a four-item "must be measured before Accepted" list. RF-DETR is recorded as the considered-and-rejected alternative with reasons. Traceability is strong. |

**Lens average: 2.75 — every criterion ≥2 → PASS.**

---

## Lens: ML / Architecture-of-the-model (§3.2 applied to the ML choice + §3.1 framing)

| Criterion | Score | Notes |
|---|---|---|
| Model choice defensible vs alternatives, with reasoning | 3 | YOLO11n@320 int8 is argued on the right axis: the task is "localise one large quad + deskew," a coarse job that does not need RF-DETR's accuracy headroom, and YOLO11n wins on *mature mobile export tooling* (CoreML/TFLite), size variants, and abundant field evidence. RF-DETR nano is named, credited ("excellent accuracy-for-size"), and rejected for concrete reasons, not dismissed. The two FPS levers (320 vs 640 ≈ 4× compute; int8) are correctly identified, and the int8 accuracy cost (~7 mAP) is explicitly waved off as irrelevant to localisation but material to the *cloud* fine-classification it deliberately keeps off-device. This is a genuinely reasoned choice. |
| FPS numbers real/sourced vs fabricated | 2 | The *flagship* numbers are sourced to specific, plausible artifacts (Qualcomm AI Hub YOLOv11 sizes 10.1 MB float / 2.83 MB W8A8; S23/8-Gen-2 ~5.4–6.7 ms; iPhone NE ~85 FPS CoreML vs ~21 PyTorch; 60+ FPS quantized) — these match the public corpus as of the cutoff and are not invented. The *mid-range ~32 ms* is explicitly an estimate, repeatedly flagged as such ("Read this as a map of bands, not a promise"), and decomposed into sourced-inference + plausible pre/post rather than asserted whole. Held to 2 not 3 because the mid-range inference component (~22 ms GPU-delegate) is the single number with the weakest citation — it is interpolated from "the corpus is flagship-heavy," not pinned to a specific mid-range measurement. That is the correct honest move, but it is still the soft spot, and the ADR rightly makes it the one thing the hardware benchmark exists to settle. |
| Flagship-vs-mid-range distinction honest, not overclaimed | 3 | This is the spike's strongest quality. It states outright that "almost nobody publishes mid-range detection numbers," refuses to launder flagship FPS into a mid-range promise, puts the mid-GPU row "right on the 33 ms knife-edge," and frames the whole thing as build-approved/floor-FPS-pending with a tier ladder as the hedge. The negative consequences section leads with the knife-edge risk. No overclaim; if anything it under-promises the floor device. |
| Benchmark protocol concrete enough to execute | 3 | FINDINGS gives named reference devices per band (A54/A34/A33 as "the decider," not a device zoo), five specific measurements (end-to-end latency broken into pre/inference/NMS, sustained 60 s FPS *plus thermal re-measure*, stack throughput with false-commit/missed-card rates, recall on a fixed ~200-image hard set at 320 vs 416, battery/memory over 10 min), and a pass/investigate/fail threshold table that feeds back into the *same* `fps_budget.py` model. It specifies "inside a VisionCamera frame processor, not a synthetic loop" and "react-native-fast-tflite" — i.e. it pre-empts the most common way these benchmarks lie. This is executable as written. |
| Risk framing / unmeasured-risk surfaced honestly (§3.1) | 3 | Five riskiest-unknowns, the gating one named first; pre/post-rivals-the-model and NNAPI-slower-than-CPU both surfaced; recall flagged as a first-class pass/fail so "FPS means nothing if it misses skewed cards." The "does this invalidate a core assumption?" section correctly concludes no plan-level fork because the architecture already assumed the split. Disciplined. |

**Lens average: 2.8 — every criterion ≥2 → PASS.**

---

## Helper script (§3.3, scoped to the one script)

`fps_budget.py` is idiomatic, fully typed, frozen dataclasses, `from __future__ import annotations`, real input validation (`total_ms` rejects ≤0; `required_sample_fps` rejects non-positive dwell/frames and out-of-range success rate; unsupported camera FPS rejected). Tests pin the *boundaries the design leans on* — the 33.33 ms frame-interval cliff, the `min()` camera-vs-model ceiling, the dwell-bound throughput collapse, the sample-rate inversion — and explicitly do not test sourced latencies, which are inputs not invariants. That is the right test philosophy for an estimation tool. Green. **Solid (≥2 on every applicable criterion).**

---

## Premium / Not-Generic gate (§3.6)

**Verdict: PASS — would a top-tier ML/mobile lead ship this spike? Honest yes.**

Scanned for every listed AI-tell:

- **Vague "industry standard" claims without sources:** none. Every load-bearing number carries a specific citation (arxiv IDs, Qualcomm AI Hub, Roboflow/Ultralytics, the TF NNAPI issue, VisionCamera docs). The one unsourceable number (mid-range ~32 ms) is *labelled* an estimate, not dressed as fact.
- **Essay-voice / padded prose / em-dash hype-soup:** prose is dense but every sentence is load-bearing; em-dashes are used as punctuation, not as a hype tic. No marketing voice.
- **Over-commenting narrating the obvious:** comments explain *why* (why pre/post is included, why throughput is dwell-bound, why tests pin boundaries not latencies), not *what*. No tutorial-grade narration.
- **Speculative abstraction / dead code / `foo`/`temp` naming:** none. Domain-precise naming (`confirmable_frames_per_card`, `required_sample_fps`, `card_dwell_ms`). No unused params.
- **Copy-paste drift / inconsistent house style:** consistent with the spike-A house style (ADR + FINDINGS + typed proof script + threshold tables).

The unglamorous details are present: thermal re-measure after 5 min, battery delta as a premium constraint ("premium apps don't cook the phone"), YUV-not-RGB and downscale-before-inference treated as *mandatory* not optional, the "coach don't drop" UX so a value-bearing flow never silently commits an unconfirmed card. **Zero AI-tells. Premium gate: PASS.**

---

## Prioritized findings

**P2 — minor, fix-on-touch (not gating):**

1. **Citation-numbering drift.** ADR 0003 cites `MASTER_PLAN.md §8` and `§7.3`; the actual `docs/MASTER_PLAN.md` carries the matching substance (Phase-0 on-device-FPS spike; "rapid/stack mode is ID + value only — no grade/auth") at lines 110 and 101, but not under those section numbers. The architecture doc's own spike for this is labelled **SPIKE B**, while this work unit is tracked as "Spike C" — the cross-doc spike lettering is inconsistent. Substance is intact; the pointers are imprecise. Reconcile spike IDs and section refs in one pass.

2. **The ~22 ms mid-range GPU-delegate inference figure is the model's softest input.** It is honestly labelled, but it is interpolated, not measured or sourced to a comparable part. The protocol already targets it correctly; just keep this row flagged as the single number whose error bar dominates the whole verdict, and resist quoting "~30 FPS on mid-range" externally until the A54-class measurement lands.

**P3 — nice-to-have:**

3. The frame-budget model assumes a *synchronous* frame processor (drop-frame-on-overrun). VisionCamera also offers `runAsync` (process on a separate thread, latest-frame-wins), which changes the realised-FPS math for the live-preview case. The protocol mentions `runAtTargetFps`; a one-line note that the sync-vs-async choice is itself a measured variable would close the loop.

---

## Overall verdict

| Lens | Average | Every criterion ≥2 | Result |
|---|---|---|---|
| Architecture (§3.2) | 2.75 | yes | **PASS** |
| ML (§3.2/§3.1 applied) | 2.80 | yes | **PASS** |
| Helper script (§3.3) | solid | yes | **PASS** |
| Premium gate (§3.6) | — | zero AI-tells | **PASS** |

**Spike C PASSES all applicable lenses and the Premium gate.** The cited flagship FPS numbers are real and specifically sourced; the mid-range numbers are honestly presented as estimates with the load-bearing unknown (mid-GPU end-to-end latency) correctly isolated as the one thing the hardware benchmark must settle — not overclaimed. YOLO11n@320 int8 is a defensibly-reasoned choice over RF-DETR for this coarse-localisation task. The benchmark protocol is concrete enough to execute as written and feeds back into the same model that produced the estimates. Findings are P2/P3 only — citation hygiene and a flag on the softest input — none gating. **Recommend: build-approved as the ADR itself states (floor-FPS-pending), no refine cycle required.**
