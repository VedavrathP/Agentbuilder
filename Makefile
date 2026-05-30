.PHONY: help install dev backend-dev frontend-dev demo seed test test-backend test-frontend lint clean db-up db-down migrate

help:
	@echo "Targets:"
	@echo "  install         Install backend deps locally (no Docker)"
	@echo "  db-up           Start Postgres + Redis only"
	@echo "  db-down         Stop Postgres + Redis"
	@echo "  migrate         Run alembic migrations"
	@echo "  backend-dev     Run backend (FastAPI) locally with reload"
	@echo "  frontend-dev    Run frontend (Next.js) locally"
	@echo "  demo            docker-compose up --build (everything)"
	@echo "  seed            Seed default workflow templates"
	@echo "  test            Run backend + frontend tests"
	@echo "  test-backend    Backend tests only"
	@echo "  test-frontend   Frontend tests only"
	@echo "  lint            Run ruff on backend"
	@echo "  clean           Remove venv + node_modules + caches"

install:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -e "backend[dev]"

db-up:
	docker compose up -d db redis

db-down:
	docker compose stop db redis

migrate:
	cd backend && ../.venv/bin/alembic upgrade head

backend-dev:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

demo:
	docker compose up --build

seed:
	cd backend && ../.venv/bin/python -m app.scripts.seed_templates

test: test-backend test-frontend

test-backend:
	cd backend && ../.venv/bin/pytest -v

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ../.venv/bin/ruff check app tests

clean:
	rm -rf .venv backend/.pytest_cache backend/__pycache__ frontend/node_modules frontend/.next
