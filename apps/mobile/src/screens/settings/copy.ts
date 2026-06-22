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

  currencyOverline: "CURRENCY",
  // Honest framing: prices are sourced in EUR (Cardmarket); USD is a live FX conversion, not a
  // US-market quote. The collector should never read a converted figure as a TCGplayer price.
  currencyHint: "Prices come from Cardmarket in EUR. USD is converted at today's rate — a display aid, not a US-market price.",

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
