# Spike C — findings

**Question:** can we run real-time card *detection* (locate + de-skew, run the
capture-quality gate, cheap "is this a card?") on-device at usable FPS on a **mid-range
Android** plus iOS — enough for live single-card and high-volume stack scanning — without a
server round-trip per frame? Research + planning spike; no device available, so this is a
web-evidenced engineering analysis, not a microbenchmark.

## Verdict

**Feasible — with a clear device-tier story and one number that must be confirmed on
hardware.** Decision and full reasoning in `docs/adr/0003-on-device-detection.md`.

- **iOS / flagship Android: confidently real-time.** Quantized YOLO11 hits **60–85 FPS on the
  iPhone Neural Engine** and **~5–7 ms/inference (~150+ FPS) on Snapdragon 8 Gen 2 NPU**
  (sourced). At our 320px int8 working point these are not close calls.
- **Mid-range Android live preview: the knife-edge.** The estimation model puts a 320px int8
  detector on the **GPU delegate at ~32 ms/frame end-to-end — right on the 33 ms / 30 FPS
  budget.** If the real number is better, we get smooth 30 FPS; if it's ~40–50 ms, the floor
  device gets **Tier-2 ~15–20 FPS** live preview. Either way the product works; the *flagship
  smoothness* on the floor device is the bet.
- **Stack scanning: feasible everywhere, and it's the cheap case.** Throughput is
  **dwell-bound, not inference-bound** — a **~8 FPS sampled detector with confirm-at-end**
  commits **~75–100 cards/min** and runs even on the CPU-fallback band. The hardest product
  mode degrades onto exactly the weakest devices.

### FPS band + device floor (one line)

**Floor = a 2022–2023 ~€250–350 Android (A33/A34/A54-class, GPU-delegate path).** Expected
band at 320px int8: **iOS/flagship 30 FPS (capped by camera, model is ~80+); mid-range
~20–30 FPS live preview; stack mode ~8 FPS sampled → ~75–100 cards/min across the board.**
Below the floor (no usable GPU), drop to the OpenCV-quad / tap-to-capture fallback — still
usable, not real-time.

### Recommended model (one line)

**YOLO11n, single class ("card"), 320×320, int8 (W8A8), CoreML on iOS + TFLite on Android,
GPU delegate default / NNAPI opt-in per device. Footprint < ~3 MB, bundled in-app.** RF-DETR
nano was considered (excellent accuracy-for-size) but YOLO11n wins on mature mobile export
tooling, multiple size variants, and abundant TFLite/CoreML field evidence — and our task
(localise one big quad) doesn't need RF-DETR's accuracy headroom.

## Riskiest unknowns

1. **Mid-range end-to-end latency at 320px (the gating risk).** Almost no one publishes
   mid-range detection numbers; the corpus is flagship/server-heavy. Our ~32 ms is an
   *estimate* from sourced inference + plausible pre/post. The real loop — including
   YUV→model colour-convert, resize/letterbox, and NMS — is what decides whether the floor
   device does 30 or 20 FPS. **This is the number the hardware benchmark exists to settle.**
2. **Pre/post can rival the model on slow silicon.** On a weak CPU the resize + colour-convert
   + NMS can match the inference cost. Treat "downscale-before-inference + YUV frames" as
   mandatory, and measure the *whole* loop, never inference in isolation.
3. **NNAPI is unreliable across the mid-range** — documented cases of it being *slower than
   CPU*, and int8-on-NPU occasionally slower than float. We default to the GPU delegate and
   make NNAPI an A/B-proven per-device opt-in, not an assumption.
4. **Detection recall at 320px on hard cards** (skew, glare, partial occlusion, overlapping
   stacks). FPS means nothing if a low-res detector misses skewed cards. Recall is a
   first-class pass/fail in the protocol below, weighed against the resolution we chose for
   speed.
5. **VisionCamera frame-processor reality vs a synthetic loop.** Sourced FPS come from
   tight inference loops; the real bridge cost (frame → ArrayBuffer → tflite → JS) on the
   floor device must be measured in-app, with `react-native-fast-tflite`, not extrapolated.

## On-device benchmark protocol (run once the RN app + test devices exist)

**Goal:** replace every estimate in ADR 0003 with a measured number, and either promote it to
*Accepted* or move device bands down a tier.

**Reference devices (the bands, not a zoo):**

| Band | Reference device (or class) | Why |
|---|---|---|
| iOS ceiling | iPhone 13/14 (A15/A16, Neural Engine) | confirms the 60+ FPS claim end-to-end |
| iOS floor | iPhone SE 2nd/3rd gen | cheapest in-support iOS — the real iOS floor |
| Android flagship | Galaxy S23 / Pixel 7 (8 Gen 2 / Tensor G2) | the published-NPU reference point |
| **Android floor (the decider)** | **Galaxy A54 / A34 / A33** | the €250–350 mid-range this spike is about |
| Android sub-floor | A14/A13-class, no usable GPU delegate | proves Tier-3 OpenCV fallback stays usable |

**What to measure (per device, GPU delegate / NNAPI / CPU each):**

1. **End-to-end per-frame latency** of 320px int8 YOLO11n *inside a VisionCamera frame
   processor* — break out pre / inference / NMS so we see where time goes. Also run 416px to
   know the headroom cost.
2. **Sustained live-preview FPS** over a 60 s session (not a burst), with the quality gate
   running, plus thermals: re-measure after 5 min of continuous scanning to catch throttling.
3. **Stack throughput**: real fan of ~50 known cards → cards/min, **false-commit rate**
   (committed the wrong/duplicate card) and **missed-card rate**, at slow / medium / fast fan.
4. **Detection recall** on a fixed ~200-image hard set (skew up to ±30°, heavy glare, a corner
   occluded, two-card overlap) at 320 vs 416 — recall and mean IoU of the deskew quad.
5. **Battery + memory** delta over a 10-min continuous-scan session (premium apps don't cook
   the phone).

**Pass / fail thresholds:**

| Metric | Pass (floor device) | Investigate | Fail → drop a tier / re-spec |
|---|---|---|---|
| Live-preview FPS (Android floor) | ≥ 25 FPS sustained | 18–25 FPS | < 18 FPS → Tier-2 default on floor |
| End-to-end frame latency (floor, GPU) | ≤ 33 ms | 33–50 ms | > 50 ms → 320px not enough / re-quantize |
| Stack throughput | ≥ 60 cards/min | 40–60 | < 40 → revisit confirm/dwell tuning |
| Stack false-commit rate | ≤ 1% | 1–3% | > 3% → raise frames_to_confirm |
| Detection recall (hard set, 320px) | ≥ 95% | 90–95% | < 90% → bump to 416px, re-test FPS |
| Sustained FPS after 5 min (thermal) | ≥ 80% of cold FPS | 60–80% | < 60% → cap frame-processor FPS, coach |
| Battery, 10-min continuous scan | ≤ ~8% drain | 8–12% | > 12% → throttle sample rate |

**Tooling:** `spikes/on_device_fps/fps_budget.py` already converts measured per-frame
latency → preview FPS and stack cards/min, and inverts dwell → required sample FPS — so the
benchmark feeds straight back into the same model that produced the estimates, and we compare
predicted vs measured directly.

## Does this invalidate a core assumption?

**No plan-level fork.** The architecture already assumes detection/gating on-device and
recognition in the cloud (`TECHNICAL_ARCHITECTURE.md` §1.2, §3.1, §5.3); this spike confirms
that split is sound and sharpens the *how* (320px int8 YOLO11n, GPU-delegate default, sampled
stack mode, three-tier fallback). The one residual is the mid-range live-preview FPS, which is
contained by the tier ladder: a worse-than-hoped benchmark moves the floor device to ~20 FPS
and a coached/interpolated teal-lock — it does not break the product or the cost model.
Proceed to build against this design; treat the floor-device FPS as **build-approved,
hardware-pending**, tracked for the Phase-1 device test.
