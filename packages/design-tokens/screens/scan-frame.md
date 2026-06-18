# Signature screen — Scan frame (capture-lock)

The first thing a returning collector does: point the camera at a card pulled from a shoebox. This screen is the handshake between capture and ML (master plan §7) — it must *refuse to grade a bad photo* and coach the user to a good one, all while feeling like a precision instrument, not a webcam.

The wow moment is the **teal capture-lock**: as focus, glare, and corner detection cross threshold, the frame snaps from a searching dashed outline to a solid teal bracket with a soft aura, and a single haptic fires. The collector *feels* the card click into place.

---

## Layout

Full-bleed camera preview on the Vault background. Three zones, top to bottom:

1. **Top bar** — back chevron (left), mode toggle `Scan · Stack` (center, segmented), flash (right). 44pt targets. `space.5` inset from safe area.
2. **Capture target** — a card-aspect frame (`size.card.ratio` = 0.714) centered horizontally, sitting slightly above optical center (~46% from top) so the quality chips below don't crowd it. The frame is four corner brackets, not a full rectangle — lighter, more instrument-like.
3. **Coaching strip** — quality chips in a horizontal row just under the frame, and the primary capture affordance at the bottom.

The shutter is **not** a generic round button. At rest it's a thin teal-outlined pill reading `Hold steady`; on lock it fills teal and becomes tappable `Capture`. In guided multi-angle mode it shows `1 / 3 · Front`.

---

## Quality chips

Three chips reflect the live ML capture signals. Each: dot + label, `radius.pill`, `bodySm` weight 600, on `color.semantic.dark.bgInset` at 72% opacity (so the preview reads through).

| Chip | Pass | Working | Fail |
|------|------|---------|------|
| Focus | teal dot, `Sharp` | amber, `Focusing…` | amber, `Too blurry` |
| Glare | teal, `No glare` | amber, `Tilt away from light` | amber, `Glare on holo` |
| Frame | teal, `All 4 corners` | amber, `Show full card` | amber, `Corner cut off` |

Chips never show red — a not-yet-good photo is a coaching state, not an error. Red is reserved for true system failure (camera permission denied, hardware error).

---

## Tokens used

- Background: live camera; vignette `--gradient-vault-depth` at the edges for focus.
- Frame searching: 1.5px dashed, `color.neutral.700`, corners only.
- Frame **locked**: 2.5px solid `color.semantic.dark.lock` (teal) + `--gradient-lock-glow` behind it.
- Chip pass: `color.teal.400` dot, `color.neutral.900` text. Working/fail: `color.support.amber`.
- Shutter rest: `color.teal.400` 1.5px ring, transparent fill, `label` text. Locked: teal fill, `color.neutral.0` text.
- Corner radii: frame brackets `radius.sm`; chips `radius.pill`; shutter `radius.pill`.
- Type: chips `bodySm`/600; shutter `label`; mode toggle `caption`/600 uppercase via `overline` tracking.

---

## Motion choreography

| Step | Property | Duration · easing |
|------|----------|-------------------|
| Frame searching | corner brackets breathe scale 1.0→1.015 loop | 1600ms `standard`, alternate |
| Quality crossing threshold | each chip dot amber→teal | `fast` `standard` |
| **Lock snap** | dashed→solid, brackets scale 1.04→1.0, glow fade-in 0→1 | `base` `spring` |
| Lock haptic | single `medium` impact on snap | — |
| Shutter enable | ring→fill, label crossfade | `base` `standard` |
| Capture | frame flash white 8% then collapse toward center | `fast` `exit` |
| Refuse-to-grade | if user taps Capture while unlocked: shutter shakes ±4px ×2, the failing chip pulses | `instant` ×2 `spring` |

`prefers-reduced-motion`: drop the breathing loop and the lock scale; keep the color crossfade and glow (state legibility), no shake — replace with a static failing-chip highlight + the coaching toast.

---

## States

- **Searching** (default) — dashed frame, chips mixed amber/teal, shutter says `Hold steady`, disabled.
- **Locked** — solid teal frame + glow, all chips teal, shutter `Capture` enabled.
- **Multi-angle guided** — after front capture, frame shows `2 / 3 · Tilt left 15°` with a small tilt indicator; required for pre-grade/anti-fake per §7.3.
- **Stack mode** — ID + value only; a persistent caption `Fast mode — value only, no grade` sets expectations honestly.
- **Refused** — sub-threshold capture attempt → toast `Let's get a cleaner shot — {reason}` anchored above the shutter, `color.support.amber` left rule. Never blames the user.
- **No-card / empty** — frame searching >6s with nothing detected → quiet hint `Lay the card on a flat, dark surface`.
- **Permission denied** — full-screen Vault state, `displayMd` `Camera access needed`, body explaining why, button `Open settings`. This is the one red-adjacent system state.

---

## Accessibility

- Quality state is announced, not just colored: each chip carries an SR label `Focus: sharp` / `Glare: tilt away from light`. Color is never the sole signal — the label text changes too.
- Lock announces `Card locked — ready to capture` via live region (polite).
- Shutter disabled state has `aria-disabled` + an SR hint describing what's missing.
- 44pt minimum on every control; shutter is 56pt tall.
- Contrast: teal `#23D5C7` chip text uses `neutral.900` on dark inset (AA for `bodySm`); amber chips likewise.
