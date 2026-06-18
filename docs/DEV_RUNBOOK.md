# Holofy — Dev Runbook

How to run Holofy in **dev mode**. Everything here runs **mock-first, with no API keys** — the real
providers (recognition, pricing, auth, billing) drop in behind their seams later (see `BLOCKERS.md`).

Top-level `make help` lists every command.

## Prerequisites
- Python 3.12, Node 22+. (No Docker required.)
- Backend deps are vendored into `apps/api/.deps` (install path documented in `apps/api/README.md`:
  `pip install --target .deps -r requirements.txt`, or a normal venv).
- Mobile deps: `cd apps/mobile && npm install` (pulls Expo/React Native — needs the native toolchain;
  not installable in the sandbox CI, but standard on a dev machine).

## Backend (the whole API, mock-first)

```bash
make api-dev      # boot the API on http://127.0.0.1:8099 (auto-migrates, --reload)
make api-smoke    # fresh DB -> boot -> drive the FULL user journey over HTTP -> tear down
make api-test     # backend test suite
```

`make api-smoke` is the end-to-end proof. It mints a dev bearer token and walks the real product:

```
health        : ok · region eu-central-1
authz guard   : no token -> 401 (expected 401)
scan (high)   : resolved -> Tidecaller Leviath (Origins Vault 8/120) @ €289.00
scan (low)    : needs_confirmation -> confirm €757.10 vs €24.50 · delta €732.60
collection add: Tidecaller Leviath @ €289.00
portfolio     : 1 item(s) · total €289.00
pre-grade     : likely 5-9 (P(>=6)=0.65) · conf 0.3
authenticity  : strong_signals · evidence conf 0.922 · recommend_authentication=True (risk flag, no verdict)
consent       : set granted=True · reads back granted=True (account-level)
```

Interactive docs: with `make api-dev` running, open `http://127.0.0.1:8099/docs` (OpenAPI/Swagger).

### Minting a dev token by hand
```bash
cd apps/api && PYTHONPATH=.deps:. python3 -c \
 "from app.auth.dev_token import mint_dev_token; from app.config import INSECURE_DEV_SECRET; \
  print(mint_dev_token('me', secret=INSECURE_DEV_SECRET))"
# then: curl -H "Authorization: Bearer <token>" http://127.0.0.1:8099/portfolio
```
The dev-token backend is genuinely user-scoped (HMAC-signed; distinct subjects = distinct users).
Outside `local`, the app refuses to boot on the default secret (a real `HOLOFY_AUTH_DEV_SECRET` is required).

## Mobile (Expo / React Native)

```bash
make mobile-test        # node --test suite
make mobile-typecheck   # tsc --strict --noEmit (must be 0 errors)
make tokens             # rebuild the design-token package
cd apps/mobile && npx expo start   # run on a simulator/device (needs npm install + toolchain)
```

The app runs **fixture-backed by default** (renders every screen with no backend). To point it at the
local API, set the provider to HTTP mode in `apps/mobile/src/api/ApiProvider.tsx`:

```tsx
<ApiProvider mode="http" baseUrl="http://localhost:8099" devToken={DEV_TOKEN}>
```
(Use your machine's LAN IP instead of `localhost` when running on a physical device.)

## What "dev mode ready" means here vs. what's left
- **Ready now:** backend boots and serves the full journey live (mock-first); mobile compiles clean under
  strict TS, all suites green, every screen renders fixture-backed, and the HTTP seam points at the local API.
- **Needs the founder's resources (`BLOCKERS.md`), not code:** real recognition/pricing keys, OAuth, billing,
  Redis, EU cloud, `expo-camera` device capture, and the legal price-display clearance. Each is a config/seam
  swap, not a rewrite — that's the point of the provider architecture.
