// Settings copy, kept apart from layout so the words read as words. Plain, specific, no
// marketing voice — a money-and-trust surface.

export const settingsCopy = {
  overline: "SETTINGS",
  title: "Account",

  // Shown only in the demo (no signed-in account). In live mode the real email replaces it.
  accountName: "Collector",
  accountStatus: "Free during the beta",

  appearanceOverline: "APPEARANCE",
  appearanceHint: "System follows your device. Light and Dark override it.",

  planRowLabel: "Plan",
  planRowValue: "Free (beta)",
  planRowHint: "Everything's free while Holofy is in testing.",

  privacyRowLabel: "Privacy & training",
  privacyRowValue: "Manage what improves Holofy",

  // The non-affiliation line is a launch-gate legal requirement (master plan §6), surfaced
  // calmly at the foot of Settings rather than buried.
  legal:
    "Holofy is a collector's tool. It is not affiliated with, endorsed by, or sponsored by Nintendo or The Pokémon Company.",
} as const;
