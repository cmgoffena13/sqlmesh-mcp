.PHONY: install ready format lint type-check test test-cov compile

install:
	uv sync --all-extras
	uv run -- prek install
	cp .env.example .env

run:
	uv run -- python main.py

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

compile:
	rm -rf dist
	uv run --no-dev -- nuitka src/app.py \
		--standalone \
		--onefile \
		--lto=yes \
		--assume-yes-for-downloads \
		--output-filename=sqlparse \
		--python-flag=no_warnings \
		--include-package=src \
		--include-package=certifi \
		--include-package-data=certifi \
		--include-distribution-metadata=caio \
		--include-distribution-metadata=aiofile \
		--nofollow-import-to=src.tests \
		--nofollow-import-to=pytest \
		--nofollow-import-to=fastmcp.cli \
		--include-data-files=pyproject.toml=pyproject.toml \
		--include-data-files=src/schema.sql=src/schema.sql \
		--include-data-files=src/drop_schema.sql=src/drop_schema.sql \
		--noinclude-data-files=src/tests/* \
		--output-dir=dist/