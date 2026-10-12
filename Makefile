.PHONY: install ready format lint type-check test test-cov

install:
	uv sync --all-extras
	uv run -- prek install
	cp .env.example .env

ready: lint format type-check test-cov

format:
	uv run -- ruff format

lint:
	uv run -- ruff check --fix

type-check:
	uv run -- ty check

test:
	uv run -- pytest -v -n auto

test-cov:
	uv run -- pytest --cov=src --cov-report=term-missing

upgrade:
	uv sync --upgrade --all-extras