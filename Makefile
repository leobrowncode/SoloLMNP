.PHONY: test lint typecheck up
up:
	docker compose up --build
test:
	cd backend && pytest
	cd frontend && npm test
lint:
	cd backend && ruff check .
	cd frontend && npm run lint
typecheck:
	cd backend && mypy app
	cd frontend && npm run typecheck
