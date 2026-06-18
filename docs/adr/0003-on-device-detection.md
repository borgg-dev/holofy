# ADR 0003 — On-device card detection: quantized YOLO11n at 320px, detect-and-gate on device

- **Status:** Proposed — research-backed; FPS floor must be confirmed on real hardware (see Consequences)
- **Date:** 2026-06-18
- **Deciders:** ML/Mobile lead (Spike C)
- **Relates to:** `docs/TECHNICAL_ARCHITECTURE.md` §2 (stack), §3.1 (on-device detector),
  §5.3 (COGS lever), §7 SPIKE B; resolves the Phase-0 "on-device FPS on mid Android" line
  in `MASTER_PLAN.md` §8.

## Context

The architecture (§1.1, §1.2) puts a hard seam between the phone and the cloud:
**detection, de-skew and the capture-quality gate run on-device; recognition, pricing,
pre-grade and anti-fake run in the cloud.** That seam only pays off — for both UX and
COGS (§5.3) — if the on-device half is genuinely real-time. Two questions decide it:

1. **Live single-card scan.** Can we locate a card in the camera frame, de-skew it, and
   run focus/glare/framing/"is this a card?" checks fast enough that the teal scan-frame
   locks smoothly (the Design "wow" moment), on a **mid-range Android** and on iOS —
   without a per-frame server round-trip?
2. **High-volume stack scan.** Can we fan a stack of cards past the lens and commit each
   one (ID + value only, per `MASTER_PLAN.md` §7.3 — no grade/auth in rapid mode) without
   shipping every frame to the cloud (which would blow up the §5.3 power-user cost risk)?

No physical device is available in Phase 0, so this ADR reasons forward from **published
per-inference latencies** and a frame-budget model (`spikes/on_device_fps/fps_budget.py`),
and states plainly what must still be measured on hardware (FINDINGS.md benchmark protocol).

### What "mid-range Android" means here

The device floor is a budget. We target a **2022–2023 ~€250–350 handset** — e.g. a Samsung
Galaxy A33/A34/A54 class part (Exynos 1280 / Dimensity 1080 / Snapdragon 6-series) — with a
**modest or absent usable NPU** and a competent mobile GPU. Flagships (Snapdragon 8 Gen 2,
Apple A16/A17) are the *ceiling*; the floor is the device that has to stay usable, and the
sub-floor (no usable GPU acceleration) is where the fallback in this ADR kicks in.

## What the evidence says

### Per-inference latency — the model is not the bottleneck on good silicon

YOLO11n is a 2.64M-parameter detector; Qualcomm's published artifact lists it at **10.1 MB
float / 2.83 MB at W8A8 (int8) for 640×640 input** (Qualcomm AI Hub). On the NPU of a
Snapdragon 8 Gen 2 (Galaxy S23), independent profiling puts a YOLO11 detector at
**~5.4–6.7 ms per inference** via TFLite — i.e. the *model* is ~150–180 FPS-capable on
flagship silicon. On the **iPhone Neural Engine**, a CoreML-exported YOLO11 is reported at
**~85 FPS** (vs ~21 FPS for the same model on-device under PyTorch), and Roboflow/Ultralytics
both report **60+ FPS** for quantized YOLO11 on the Neural Engine for live video. These are
flagship numbers and they are comfortably real-time.

The honest part: **mid-range is a different story, and almost nobody publishes mid-range
detection numbers** — the public benchmark corpus is flagship-and-server heavy. The two
load-bearing mid-range realities from the literature:

- **The CPU path is too slow for 30 FPS at 640px.** Generic mid-range CPU inference for a
  nano detector at 640 lands in the tens of ms *plus* pre/post; sustaining 30 FPS (a 33.3 ms
  budget — VisionCamera drops frames past it) is not reliable on CPU alone.
- **The acceleration story is fragmented and not free.** On Android, the GPU delegate is the
  most *portable* accelerator; NNAPI is inconsistent and on some chips is **slower than CPU**
  (documented regressions on e.g. Snapdragon 660-class parts), and int8 on the NPU can be
  *marginally slower* than float on some stacks. So we cannot assume "NPU = fast" on the
  floor device; we must treat the **GPU delegate as the mid-range workhorse** and NNAPI as a
  per-device opt-in proven by A/B test, not a default.

### The two levers that actually buy the FPS: input resolution and the int8 GPU path

The single biggest lever is **input resolution**, and we do not need 640. Card localisation +
quality gating is a coarse task (find one large quad, measure blur/glare); **320×320 roughly
quarters the compute vs 640×640** for the same architecture. Combined with int8 quantization
(int8 costs ~7 mAP on COCO per the YOLO11 study — irrelevant for "where is the one card",
material only for fine classification, which we deliberately keep in the cloud), 320px int8
on the GPU delegate is the configuration that brings the mid-range floor into budget.

### Frame-budget model (estimation, sourced inputs)

Feeding plausible per-frame totals (sourced inference + realistic resize/letterbox +
NMS/decode) into `fps_budget.py` at **320px** gives the design envelope:

| Device band | inference + pre + post | raw FPS | preview @30 cap | fits 33 ms? |
|---|---|---|---|---|
| iPhone Neural Engine (int8) | ~7 + 3 + 2 = 12 ms | ~83 | **30** | yes |
| Flagship Android NPU (int8) | ~6 + 4 + 3 = 13 ms | ~77 | **30** | yes |
| **Mid Android, GPU delegate (int8)** | **~22 + 6 + 4 = 32 ms** | **~31** | **~30** | **borderline-yes** |
| Mid Android, CPU fallback | ~45 + 8 + 5 = 58 ms | ~17 | ~17 | no |
| Low-end, CPU only | ~80 + 12 + 8 = 100 ms | ~10 | ~10 | no |

Read this as a *map of bands*, not a promise: the mid-range GPU row is the one sitting right
on the 33 ms knife-edge, which is exactly why it is the number the hardware benchmark must
confirm or refute. The pre/post column is deliberately not zero — on a slow part the
resize/colour-convert can rival the model, and **YUV (not RGB) frames + downscale-before-
inference are mandatory**, not optimisations (VisionCamera frame-processor guidance).

### Stack scanning does *not* need 30 FPS continuous inference

This is the most important design finding and it dissolves the hardest case. Stack throughput
is **dwell-bound, not inference-bound**: a card is only in frame for a fraction of a second,
and we commit it after a few clean, deduped detections — we do not need to infer on every
camera frame. Inverting the budget model (`required_sample_fps`):

| Card dwell in frame | sampling FPS needed for a 3-frame confirm (70% gate pass) |
|---|---|
| 400 ms (fast fan) | ~10.7 FPS |
| 600 ms | ~7.1 FPS |
| 800 ms (comfortable) | ~5.4 FPS |
| 1200 ms (deliberate) | ~3.6 FPS |

So a **throttled ~8 FPS sampled detector** (VisionCamera `runAtTargetFps`) commits a card per
~600–800 ms dwell, i.e. **~75–100 cards/min**, with the operator coached to slow down if they
fan faster than the gate can confirm. An ~8 FPS path is reachable even on the CPU-fallback
band — meaning **stack mode degrades gracefully onto exactly the devices that can't sustain
30 FPS live preview.** The expensive case is the cheap case.

## Decision

**Run detection + de-skew + the capture-quality gate fully on-device with a quantized
YOLO11n single-class card detector at 320×320 int8, exported to CoreML (iOS) and TFLite
(Android). On Android the GPU delegate is the default accelerator; NNAPI is opt-in per device,
gated by an on-device A/B probe. Live preview runs the detector throttled to the camera rate;
stack mode samples at ~8 FPS and confirms-at-end. Recognition and every fine-grained model
stay in the cloud, unchanged.**

### Model + size + quantization

- **Model:** **YOLO11n**, retrained single-class ("card") on our reference-DB images +
  synthetic augmentation (rotation, glare, partial occlusion, stack overlap). One class keeps
  the head trivial; the job is *localisation + a deskew quad*, not classification.
- **Input:** **320×320** (the resolution lever above). Revisit 416 only if 320 misses small
  or skewed cards in the benchmark.
- **Quantization:** **int8 (W8A8)** for the shipped model; keep an fp16 build for the A/B
  probe and as an accuracy reference.
- **Footprint:** a 320px int8 YOLO11n lands **well under ~3 MB** of weights (the 640px int8
  artifact is 2.83 MB per Qualcomm AI Hub; 320px is smaller). This bundles in the app with
  no material download — important for the §3.6 premium first-run.

### The on-device ↔ cloud split (unchanged from the architecture, now load-bearing)

On-device, per `TECHNICAL_ARCHITECTURE.md` §1.2 steps 1–2: locate the card, compute the
de-skew homography, run the blur/glare/framing/lighting gate, do the cheap "is this a card?"
pass, and **only upload a deskewed crop of a frame that passed the gate.** Recognition,
variant disambiguation, pricing, pre-grade and anti-fake stay in the cloud (steps 3–8). The
on-device model never tries to *name* the card — that is the cloud's job and the data-loop's
moat (§3.1). This split is precisely the §5.3 cost lever: bad and duplicate frames never
become a paid API call.

### Stack-scanning throughput design

1. **Sample, don't stream.** `runAtTargetFps(~8)` inside the VisionCamera frame processor;
   never infer on every frame. (Sourced budget: ~8 FPS covers a 3-frame confirm down to a
   ~600 ms dwell.)
2. **Confirm-at-end.** A card is *candidate* on first clean detection and *committed* only
   after `frames_to_confirm` (start at 3) deduped, gate-passing detections agree — then a
   single best crop is queued for cloud recognition.
3. **On-device dedupe before any upload.** Hash/embed the deskewed crop (perceptual hash or a
   tiny on-device embedding) and suppress near-duplicates within a short window, so re-seeing
   the same card mid-fan does not re-bill recognition (§5.3 dedupe control).
4. **Coach, don't drop.** If the operator fans faster than the gate can confirm
   (`can_confirm()` false for the current dwell), the UI slows them down — we never silently
   commit an unconfirmed card in a value-bearing flow.
5. **Rapid mode is ID + value only** (`MASTER_PLAN.md` §7.3): no grade/auth on stack frames;
   those require the deliberate multi-angle capture flow.

### Fallback for low-end / no-GPU devices

A three-tier ladder, selected at runtime from a one-time on-device capability probe (try GPU
delegate → NNAPI → CPU, keep the fastest that passes a latency threshold):

- **Tier 1 (NE / flagship NPU / mid GPU delegate):** full real-time live preview (~30 FPS),
  smooth teal-lock, stack at the full ~8 FPS sample rate.
- **Tier 2 (mid CPU fallback, ~15–20 FPS):** live preview runs the detector throttled to
  ~12–15 FPS — the teal-lock animation is driven on the UI thread and interpolated so it still
  *feels* smooth even though detections arrive slower; stack mode unaffected (it only needs ~8).
- **Tier 3 (low-end / no usable GPU):** **drop continuous detection.** Fall back to a
  **classic OpenCV largest-quad contour detector** for framing (cheap, no model) feeding the
  same quality gate, and/or a **tap-to-capture** flow with a single post-capture on-device
  detect+deskew. Mobile business-card quad segmentation at this class is documented at ~97%
  with negligible compute, so framing stays usable without the neural detector. Stack mode on
  Tier 3 runs the ~8 FPS sampled path if it holds, else single-capture.

This keeps the *product* working on the floor device even where the *flagship experience*
isn't reachable — and it means the FPS uncertainty is contained: a worse-than-expected
benchmark moves devices down a tier, it does not break the app.

## Consequences

**Positive**

- Detection + gating cost ~€0 marginal and add no server round-trip on the hot path — the
  §5.3 COGS lever is realised from day one, not deferred to "later on-device models."
- The hardest case (high-volume stack) is the *cheapest* on-device, because it is dwell-bound
  and runs at ~8 FPS — it degrades onto the exact devices that can't do 30 FPS live.
- Sub-3 MB int8 model bundles with the app; no first-run model download.
- The on-device/cloud seam stays clean: swapping the cloud recognizer (Ximilar → in-house)
  never touches the detector, and vice-versa.

**Negative / risk**

- **The mid-range GPU row sits on the 33 ms knife-edge.** If the real number lands at ~40–50 ms,
  the floor device gets Tier-2 (~15–20 FPS) live preview, not 30. The product still works; the
  *flagship* teal-lock smoothness does not reach the floor. **This is the one thing the
  hardware benchmark exists to settle.**
- NNAPI is unreliable across the mid-range; we carry GPU-delegate + CPU paths and a per-device
  probe, which is real engineering surface, not a flag.
- Pre/post-processing (resize, YUV→model colour, NMS) can rival the model on slow silicon and
  is the easiest thing to get wrong; it must be measured as part of the loop, not assumed ~0.

**What must be measured on real hardware before this is "Accepted" (see FINDINGS.md)**

1. End-to-end per-frame latency (pre + inference + post) of 320px int8 YOLO11n on the
   reference floor device, on GPU delegate vs NNAPI vs CPU.
2. Sustained live-preview FPS inside an actual VisionCamera frame processor (not a synthetic
   loop) on the floor device.
3. Stack throughput (cards/min) and false-commit / missed-card rates at real fan speeds.
4. Detection recall on skewed / glare / partially-occluded / overlapping-stack cards at 320px
   — the accuracy side the FPS story must not hide.

Until those four are green on the floor device, treat this ADR as **build-approved,
floor-FPS-pending**, and carry the Tier ladder as the hedge.

## References

- Qualcomm AI Hub — YOLOv11-Detection (2.64M params; 640×640; float 10.1 MB / W8A8 2.83 MB /
  W8A16 3.30 MB; NPU op coverage) — https://aihub.qualcomm.com/models/yolov11_det ,
  https://huggingface.co/qualcomm/YOLOv11-Detection
- Galaxy S23 / Snapdragon 8 Gen 2 YOLO11 TFLite-NPU latency (~5.4–6.7 ms) and Android AI
  inference / delegate behaviour — https://arxiv.org/html/2511.13453v1 ,
  https://huggingface.co/qualcomm/YOLOv11-Segmentation
- iPhone Neural Engine YOLO11 CoreML (~85 FPS vs ~21 FPS PyTorch; 60+ FPS quantized live) and
  iOS model selection — https://blog.roboflow.com/best-ios-object-detection-models/ ,
  https://www.ultralytics.com/blog/best-object-detection-models-for-ios-apps-on-apple-silicon-chips ,
  https://docs.ultralytics.com/models/yolo11
- int8 vs dynamic-quant accuracy cost on YOLO11 (~7.2 mAP int8 average) and YOLO evolution —
  https://arxiv.org/html/2510.09653v2 , https://arxiv.org/html/2411.00201v1
- NNAPI inconsistency / slower-than-CPU regressions; GPU delegate as portable accelerator —
  https://github.com/tensorflow/tensorflow/issues/28283 , https://ai.google.dev/edge/litert/performance/delegates
- RF-DETR nano (mobile-feasible accuracy, ~2.32 ms on optimised GPU) as the considered
  alternative — https://blog.roboflow.com/rf-detr-nano-small-medium/
- VisionCamera frame-processor budget (33 ms @30 FPS, runAtTargetFps/runAsync, downscale +
  YUV) and react-native-fast-tflite — https://react-native-vision-camera.com/docs/guides/frame-processors ,
  https://react-native-vision-camera.com/docs/guides/frame-processors-tips
- Classic OpenCV largest-quad document/card detection (Tier-3 fallback) and ~97% mobile
  business-card segmentation — https://scanbot.io/blog/ml-kit-vs-opencv-document-scanning-software/ ,
  https://arxiv.org/pdf/1101.0457
