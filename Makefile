# Holofy dev commands. Mock-first: everything here runs with no API keys.
# Backend deps live in apps/api/.deps (see apps/api/README.md); mobile uses npm.

.PHONY: help api-dev api-smoke api-test mobile-test mobile-typecheck tokens dev-check

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-16s %s\n", $$1, $$2}'

api-dev: ## Boot the API on :8099 (mock-first, no keys)
	cd apps/api && PYTHONPATH=.deps:. python3 -m alembic upgrade head && \
	PYTHONPATH=.deps:. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8099 --reload

api-smoke: ## Boot a fresh API and drive the full user journey over HTTP, then tear down
	cd apps/api && bash scripts/dev_smoke.sh

api-test: ## Run the backend test suite
	cd apps/api && PYTHONPATH=.deps:. .deps/bin/pytest -q

mobile-test: ## Run the mobile test suite
	cd apps/mobile && npm test

mobile-typecheck: ## Strict TypeScript check on the mobile app
	cd apps/mobile && npx tsc --noEmit

tokens: ## Rebuild the design-token package (TS + CSS + dist)
	cd packages/design-tokens && node build.mjs

dev-check: api-test mobile-test mobile-typecheck api-smoke ## Everything that must be green: tests + typecheck + live smoke
	@echo "dev-check OK"
