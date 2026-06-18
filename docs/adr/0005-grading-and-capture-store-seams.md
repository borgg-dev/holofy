# ADR 0005 — Grading and capture-store seams: bought sub-scores in, in-house centering kept out

- **Status:** Accepted (build-approved, documented retroactively). Carried polish task #11 —
  the P2.1 pre-grade slice shipped these seams without an ADR; this records the decision.
- **Date:** 2026-06-18
- **Deciders:** Backend lead (P2.1)
- **Relates to:** `docs/TECHNICAL_ARCHITECTURE.md` §3.2 (pre-grade: build centering, buy
  corners/edges/surface), §1.2 step 7; charter §3.1 (honest probabilistic framing), §3.2
  (ML stages swappable buy→build). Builds on the provider seam (ADR 0001) and the auth/quota
  seams (ADR 0004).

## Context

Pre-grade (P2.1) is a hybrid by design (architecture §3.2): **centering is built in-house**
(classic CV, the cheapest and most mathematically honest signal — promoted from Spike D),
while **corners, edges and surface are bought first** (Ximilar `/v2/grade`) and built later as
data accrues. Two boundaries had to be drawn so the bought half is swappable without leaking
into the rest of the service, and so the in-house half is never mistaken for a rented output:

1. **What the bought grader returns**, and where the line sits between bought and built. If
   the grader returned all four PSA axes, the in-house centering measurement — the one signal
   we can audit pixel-by-pixel and the headline feature — would be indistinguishable from a
   vendor's number, and a vendor swap could silently change it.
2. **How a capture reference becomes pixels.** The endpoints take a *reference* to an
   already-uploaded capture, never the bytes (data minimization, §6); centering genuinely
   needs pixels, so something must resolve the reference — and that something must be mockable
   so the whole flow runs with no object storage and no network.

## Decision

Two narrow Protocols, mirroring the recognition/pricing provider seam (ADR 0001).

- **`GradingProvider`** (`app/providers/base.py`) returns **only the three bought sub-scores**
  — `corners`, `edges`, `surface` — each a `SubScore` (score + the provider's own confidence
  in that read). **Centering is deliberately absent from this seam.** It is measured in-house
  (`app/grading/centering.py`) and composed in by the service (`app/services/pregrade.py`), so
  a bought-vs-built swap can never touch it. The real Ximilar provider drops in behind this
  exact signature later; the service never knows whether a sub-score was bought, built, or
  mocked. The factory (`build_grading_provider`) selects the backend by
  `HOLOFY_GRADING_PROVIDER` with a loud `case _:` on an unwired enum value.
- **`CaptureStore`** (`app/grading/capture_store.py`) resolves a `capture_ref` to image bytes,
  raising `CaptureNotFoundError` on an unknown/expired upload. The mock synthesises
  deterministic labelled card images keyed on the ref (centred, off-centre, full-bleed),
  exactly mirroring how `MockRecognitionProvider` keys fixtures on `bundle_id` — so tests drive
  every branch by reference alone. The real EU-region object-storage client drops in behind the
  same Protocol.

The honesty contract lives in the **composition**, not in copy: the worst sub-grade gates the
estimate, the distribution's spread widens as confidence drops, and a capture too poor to
measure refuses with a `retake` signal rather than a confident wrong range (charter §3.1).
The output is a `GradeProbabilityRange` — there is no field that holds "the grade".

## Consequences

- The bought half is swappable in one factory line; the built half (centering) is insulated
  from any vendor swap and stays independently auditable — the buy→build path (§3.2) is real,
  not aspirational.
- Mock provider + mock capture store mean the entire pre-grade slice — and its tests — run
  with no keys, no network, and no object storage.
- `MockGradingProvider` defaulting unknown refs to the *low-confidence* fixture means a caller
  hits the harder path (widen-the-range / refuse) unless they opt into an easy one — the
  honesty branches are exercised by default.
- `GradingBackend` has only `mock` today; adding Ximilar is a factory case + a config value,
  no endpoint or service edits. The capture store has no config switch yet (one mock); when
  the real client lands it gets the same `*_provider`-style selection.
- The seam is the template the P3.1 authenticity work mirrors (ADR 0006): a provider for the
  rented/learned signals, with the deterministic, auditable signal kept out of it.
