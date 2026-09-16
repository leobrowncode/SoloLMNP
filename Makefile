.PHONY: check test lint typecheck build migrate up down docker-smoke
PYTHON ?= python
NPM ?= npm

check:
	$(PYTHON) scripts/check.py

up:
	docker compose up --build --wait

down:
	docker compose down

migrate:
	cd backend && $(PYTHON) -m alembic upgrade head

test:
	cd backend && $(PYTHON) -m pytest
	cd frontend && $(NPM) test

lint:
	cd backend && $(PYTHON) -m ruff check .
	cd backend && $(PYTHON) -m ruff format --check .
	cd frontend && $(NPM) run lint

typecheck:
	cd backend && $(PYTHON) -m mypy app
	cd frontend && $(NPM) run typecheck

build:
	cd frontend && $(NPM) run build

docker-smoke:
	$(PYTHON) scripts/docker_smoke.py
