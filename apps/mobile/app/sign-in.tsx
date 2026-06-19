import { SignInScreen } from "@/screens/auth/SignInScreen";

// The auth gate route. Reachable only in live (http) mode — the root layout redirects an
// unauthenticated session here, and away once signed in. In fixture/demo mode the app is
// never gated, so this route is simply never navigated to.
export default function SignIn() {
  return <SignInScreen />;
}
