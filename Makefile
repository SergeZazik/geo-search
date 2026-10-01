REGION ?= dnipro
COMPOSE := docker compose

.PHONY: up down logs import test lint fmt

up:  ## Start PostGIS, run migrations and start the API
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

import:  ## Load OSM data for a region: make import REGION=kyiv (default: dnipro)
	$(COMPOSE) run --rm --build importer import --region $(REGION)

test:  ## Needs Docker: tests start their own PostGIS container
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

fmt:
	uv run ruff check --fix .
	uv run ruff format .
