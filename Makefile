# Developer shortcuts for ReBT-Rank (Task A2).
# Linting/formatting/type-checking are driven through pre-commit so the tool
# versions match CI exactly. `test`, `docs`, and `build` target dependencies
# introduced by later tasks and are provided here as stable entry points.
.DEFAULT_GOAL := help
.PHONY: help install install-dev hooks-install lint format test docs build clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Editable install of the package
	python -m pip install -e .

install-dev:  ## Install the package plus dev tooling and the git hook
	python -m pip install -e . pre-commit
	pre-commit install

hooks-install:  ## Install the git pre-commit hook
	pre-commit install

lint:  ## Run all pre-commit hooks (ruff, black, mypy, nbstripout) on all files
	pre-commit run --all-files

format:  ## Auto-fix lint and formatting (ruff --fix, black)
	pre-commit run ruff --all-files || true
	pre-commit run black --all-files || true

test:  ## Run the test suite (available once test deps land)
	pytest

docs:  ## Build the documentation site (available once docs deps land)
	mkdocs build

build:  ## Build sdist and wheel
	python -m build

clean:  ## Remove caches and build artifacts
	rm -rf build dist ./*.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
