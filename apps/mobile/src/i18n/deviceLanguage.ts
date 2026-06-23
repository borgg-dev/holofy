// The user's language, as a 2-letter ISO code, derived from the device locale.
//
// Holofy's catalog is indexed in English and French, and a card and its EN·FR counterpart can be
// visually identical (same art, same collector number, same name — e.g. "Pikachu"). The picture
// then can't say which market's print the user holds; their device locale can. The scan call sends
// this as an advisory hint, and the server uses it *only* to break that otherwise-unresolvable tie.
//
// Hermes ships Intl (the app already formats money with it), so we read the resolved locale rather
// than add a native localization dependency. Anything that isn't clearly French falls back to
// English — the broadest catalog — and a code the server doesn't recognize simply yields the honest
// confirm, so the fallback is safe.

const SUPPORTED = new Set(["en", "fr"]);

export function deviceLanguage(): string {
  try {
    const locale = Intl.DateTimeFormat().resolvedOptions().locale; // e.g. "fr-FR", "en-US"
    const lang = locale.split("-")[0]?.toLowerCase();
    if (lang && SUPPORTED.has(lang)) return lang;
  } catch {
    // Intl unavailable for some reason — fall through to the default.
  }
  return "en";
}
