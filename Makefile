# Snek's development lifecycle: named, composable quality gates.
#
#   make quality    every local gate, stopping at the first failure
#   make pre-push   `quality` on the exact revision being pushed, in a clean worktree
#   make help       list the targets
#
# Every target is phony, so every gate always runs. The gate's own artifacts (coverage data,
# exported requirements, built distributions) live under .quality/, so a developer's .coverage
# is never touched. Stages share those artifacts, so this Makefile runs serially even under -j;
# pytest parallelises the test stage itself. See docs/adr/0011-make-lifecycle-interface.md.

# Fixed, so a command-line override can never point the deletions below elsewhere.
override QUALITY := .quality
override DIST := $(QUALITY)/dist
REQUIREMENTS := $(QUALITY)/runtime-requirements.txt
COVERAGE := COVERAGE_FILE=$(CURDIR)/$(QUALITY)/coverage
UV_RUN := uv run --locked
UV_ISOLATED := uv run --isolated --no-project --with

.NOTPARALLEL:
.DEFAULT_GOAL := help
.PHONY: help install-hooks lock-check lint format-check typecheck check test audit build \
	check-distributions smoke-install package quality pre-push clean-quality

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

install-hooks: ## Install the commit and pre-push hooks for this checkout
	$(UV_RUN) pre-commit install --install-hooks

lock-check: ## Fail if uv.lock is out of date
	uv lock --check

lint: ## Ruff lint, without fixing
	$(UV_RUN) ruff check .

format-check: ## Ruff formatting check, without rewriting
	$(UV_RUN) ruff format --check .

typecheck: ## ty type checking
	$(UV_RUN) ty check

check: lock-check lint format-check typecheck ## Static checks: lockfile, lint, format, types

test: ## All tests with branch coverage, enforcing the coverage floor
	@mkdir -p $(QUALITY)
	$(COVERAGE) $(UV_RUN) pytest --quiet -n auto --maxprocesses=8 --dist=load \
		--cov=src/snek --cov-branch --cov-report=
	$(COVERAGE) $(UV_RUN) coverage report

audit: ## Audit the locked runtime dependencies for known vulnerabilities
	@mkdir -p $(QUALITY)
	uv export --quiet --locked --no-dev --no-emit-project --output-file $(REQUIREMENTS)
	$(UV_RUN) pip-audit --disable-pip --requirement $(REQUIREMENTS)

build: ## Build one wheel and one sdist into .quality/dist
	rm -rf $(DIST)
	uv build --out-dir $(DIST)

check-distributions: build ## Reject local artifacts in the built archives
	$(UV_RUN) python scripts/check_distribution.py $(DIST)/*.whl $(DIST)/*.tar.gz

smoke-install: check-distributions ## Install each archive in isolation and run the app
	for archive in $(DIST)/*.whl $(DIST)/*.tar.gz; do \
		$(UV_ISOLATED) "$$archive" snek --help > /dev/null && \
		$(UV_ISOLATED) "$$archive" python scripts/smoke_installed.py || exit 1; \
	done

package: smoke-install ## Build, check and install-test the distributions

quality: check test audit package ## Every local gate, stopping at the first failure

pre-push: ## Run quality on PRE_COMMIT_TO_REF (default HEAD) in a temporary worktree
	$(UV_RUN) python scripts/check_pushed_ref.py

clean-quality: ## Remove the gate's artifacts
	rm -rf $(QUALITY)
