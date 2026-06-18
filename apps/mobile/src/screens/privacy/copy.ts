// Consent copy, kept in one place so the words are reviewable as words (legal/design read
// this, not the layout). The bar (charter §3.5): plain language, honest about what's shared
// and why, explicit that it's optional and how to turn it off — no dark patterns, no
// pre-ticked framing, no "help us / everyone does" nudging. It states the trade plainly and
// lets the collector decide.
//
// A note on the version tag: it travels to the server as the consent note, so a later audit
// can tell which wording a user agreed under. Bump it when the copy below materially changes.

export const CONSENT_COPY_VERSION = "privacy-screen-v1";

export const privacyCopy = {
  screenTitle: "Your captures & training",
  overline: "PRIVACY",

  // The honest pitch — what, why, and the opt-out — without overselling.
  what: "When this is on, the photos you scan, pre-grade and authenticity-check are added to the data that improves Holofy's recognition and grading — so the app gets better at reading vintage cards in euros.",
  optional:
    "It's entirely optional. Holofy works exactly the same with it off — you keep every feature either way.",
  control:
    "You can turn it off any time. Turning it off stops future captures from being used and removes the ones already shared from our training data.",
  separate:
    "This is separate from agreeing to use the app. We never use your captures for training unless you switch this on here.",

  toggleLabel: "Help improve Holofy with my captures",
  toggleA11yOn: "Sharing captures for training is on. Double tap to turn off.",
  toggleA11yOff: "Sharing captures for training is off. Double tap to turn on.",

  // Status line under the toggle, reflecting the live count.
  statusOff: "Off — your captures stay private to your account.",
  statusOnNone: "On — new captures will help improve Holofy.",
  statusOnCount: (n: number) =>
    `On — ${n} ${n === 1 ? "capture is" : "captures are"} helping improve Holofy.`,

  // Errors are honest and reassuring — a failed toggle never silently leaves a wrong state.
  loadError: "Couldn't load your privacy setting. Check your connection and try again.",
  saveError: "Couldn't save that change. Your setting is unchanged — try again.",
  retry: "Try again",
} as const;

// The first-capture prompt: a one-time, plainly-worded offer shown after a collector's first
// scan. Off is the default — the affirmative action is the explicit opt-in, never the other
// way round. The two buttons render as visual peers (same tier), so nothing steers the eye
// toward "yes" (no dark pattern, charter §3.5).
export const firstCapturePrompt = {
  overline: "ONE QUICK THING",
  title: "Help Holofy read cards better?",
  body: "Optionally let the cards you scan improve Holofy's recognition and grading. It's off unless you choose it, changeable any time in Privacy, and the app is identical either way.",
  accept: "Yes, use my captures",
  decline: "Not now",
  acceptA11y: "Turn on sharing captures to improve Holofy",
  declineA11y: "Keep sharing off for now",
} as const;
