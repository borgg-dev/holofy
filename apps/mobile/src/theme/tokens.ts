// Re-export of the design-token source of truth so the rest of the app imports
// from one place ("@/theme") and never reaches into the package directly.
// Swapping the token package or adding a runtime transform happens only here.
import { tokens } from "@holofy/design-tokens";

export { tokens };
export type { Tokens } from "@holofy/design-tokens";
