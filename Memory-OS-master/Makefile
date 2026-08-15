.PHONY: dev test lint typecheck docker-up docker-down docker-prod api-test sdk-test test-all load-test

docker-up:      ; docker compose up --build
docker-down:    ; docker compose down
docker-prod:    ; docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
api-test:       ; cd services/api && PYTHONPATH=. python -m pytest -q
sdk-test:       ; python -m compileall packages/sdk-python/memoryos && cd packages/sdk-typescript && npm run build
test: api-test
test-all: api-test sdk-test typecheck lint
	@cd dashboard && npm run build
load-test:      ; @command -v k6 >/dev/null 2>&1 || (echo "Install k6: https://k6.io/docs/get-started/installation/" && exit 1); k6 run scripts/load/k6-smoke.js
dev:            ; cd dashboard && npm run dev
lint:           ; cd dashboard && npm run lint
typecheck:      ; cd dashboard && npm run typecheck
