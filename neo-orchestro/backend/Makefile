PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install lock lint typecheck test check migrate audit

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet --require-hashes -r requirements-dev.txt
	$(BIN)/pip install --quiet --no-deps -e .

# Regenerate hashed lock files from pyproject.toml
lock:
	$(BIN)/pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras -o requirements.txt pyproject.toml
	$(BIN)/pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras --extra dev -o requirements-dev.txt pyproject.toml

lint:
	$(BIN)/ruff format --check .
	$(BIN)/ruff check .

typecheck:
	$(BIN)/mypy

test:
	$(BIN)/pytest

check: lint typecheck test

migrate:
	$(BIN)/alembic upgrade head

audit:
	$(BIN)/pip-audit -r requirements.txt --require-hashes
