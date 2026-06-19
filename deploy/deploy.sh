#!/usr/bin/env bash
# One-command testnet deploy. Run this ON the Linode, from the repo root's deploy/ dir,
# after creating deploy/.env (see deploy/.env.example) and pointing your domain's A record
# at this box. It builds the API image, brings up Postgres + Redis + the API + Caddy, and
# Caddy fetches the HTTPS cert automatically. Re-run any time to ship a new build.
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "ERROR: deploy/.env is missing. Copy deploy/.env.example to deploy/.env and fill it in." >&2
  exit 1
fi

# Pick up DOMAIN/secrets for compose interpolation.
set -a; # shellcheck disable=SC1091
source .env; set +a

echo "==> Building and starting the stack for ${HOLOFY_DOMAIN} ..."
docker compose --env-file .env up -d --build

echo "==> Waiting for the API to report healthy ..."
for i in $(seq 1 60); do
  if curl -fsS "https://${HOLOFY_DOMAIN}/health" >/dev/null 2>&1; then
    echo "==> Live: https://${HOLOFY_DOMAIN}/health"
    echo "    Privacy: https://${HOLOFY_DOMAIN}/privacy   Terms: https://${HOLOFY_DOMAIN}/terms"
    exit 0
  fi
  sleep 3
done

echo "==> API did not report healthy yet. Check logs with:  docker compose logs -f api caddy" >&2
exit 1
