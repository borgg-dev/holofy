# Holofy testnet deploy (single Linode)

A free, closed test running on one box: API (real providers) + Postgres + Redis + Caddy
(automatic HTTPS). Card images persist to local disk.

## What you need
- A **Linode 4 GB shared CPU** running **Ubuntu 24.04 LTS** (2 GB can work but is tight under the OCR load).
- A **domain** with an **A record** pointing at the Linode's IP (e.g. `api.yourdomain.com`).
- Docker (the steps below install it).

## One-time setup on the Linode
```bash
# 1. Install Docker + compose plugin
curl -fsSL https://get.docker.com | sh

# 2. Get the code
git clone https://github.com/borgg-dev/holofy.git
cd holofy/deploy

# 3. Configure secrets
cp .env.example .env
nano .env            # set HOLOFY_DOMAIN, and paste:
                     #   openssl rand -hex 32   -> HOLOFY_AUTH_SECRET
                     #   openssl rand -hex 24   -> POSTGRES_PASSWORD

# 4. Point your domain's A record at this server's IP, then:
bash deploy.sh
```

`deploy.sh` builds the image, starts everything, and Caddy fetches the HTTPS certificate
automatically (give DNS a few minutes to propagate first). When it finishes you'll have:

- `https://YOUR_DOMAIN/health` — API health
- `https://YOUR_DOMAIN/privacy` and `/terms` — the legal pages (the Privacy URL Google Play asks for)

## Ship a new build
```bash
cd holofy && git pull && cd deploy && bash deploy.sh
```

## Point the mobile app at it
1. Edit `apps/mobile/eas.json` → `build.preview.env.EXPO_PUBLIC_API_URL` and set it to your
   deployed URL (e.g. `https://api.yourdomain.com`). This is what bakes the live backend into
   the build; with it set, the app shows the real sign-in / sign-up / account screens.
2. Build the internal Android APK:
   ```bash
   cd apps/mobile
   npx eas build --profile preview --platform android
   ```
EAS returns an install link/APK you share with testers — no Google Play account needed.

To test locally against the server before building, run the web/dev app pointed at it:
```bash
make mobile-watch-live HOLOFY_API_URL=https://api.yourdomain.com
```

## Notes for the test phase
- **Training-data lake** runs in `mock` mode (not persisted) — fine for a test; the real
  EU-region lake writer drops in behind the same seam when you go further.
- **Migrations** run on API start (single box). For multi-instance later, split them out.
- **Backups:** the `pgdata` and `captures` Docker volumes hold all state — snapshot the Linode
  or `docker run --rm -v holofy_pgdata:/v ...` to back them up.
