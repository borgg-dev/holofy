// Settings copy, kept apart from layout so the words read as words. Plain, specific, no
// marketing voice — a money-and-trust surface.

export const settingsCopy = {
  overline: "SETTINGS",
  title: "Account",

  // The account block stands in for the real auth identity (Phase 1). Honest placeholder
  // framing — never a fake email or a "John Doe", which would read as unfinished.
  accountName: "Collector",
  accountStatus: "Free plan · sign-in arrives in the next build",

  planRowLabel: "Plan",
  planRowValue: "Collector (Free)",
  planRowHint: "Upgrade to Collector+ for unlimited scans",

  privacyRowLabel: "Privacy & training",
  privacyRowValue: "Manage what improves Holofy",

  // The non-affiliation line is a launch-gate legal requirement (master plan §6), surfaced
  // calmly at the foot of Settings rather than buried.
  legal:
    "Holofy is a collector's tool. It is not affiliated with, endorsed by, or sponsored by Nintendo or The Pokémon Company.",
} as const;
