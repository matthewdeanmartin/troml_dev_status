.EXPORT_ALL_VARIABLES:

# Get package directories under src
PACKAGES := $(shell find src -mindepth 1 -maxdepth 1 -type d -not -name "__pycache__")
PACKAGE_NAMES := $(notdir $(PACKAGES))
PYTHON_TARGETS := src test
MARKDOWN_TARGETS := README.md CHANGELOG.md docs

PINACT_RUN ?= go run github.com/suzuki-shunsuke/pinact/v3/cmd/pinact@latest run

# if you wrap everything in uv run, it runs slower.
ifeq ($(origin VIRTUAL_ENV),undefined)
	VENV := uv run
else
	VENV :=
endif

.PHONY: sync
sync: pyproject.toml
	@echo "Installing dependencies"
	@uv sync

.PHONY: clean-pyc
clean-pyc:
	@echo "Removing compiled files"
	@find . -name "*.pyc" -exec rm -f {} +
	@find . -name "*.pyo" -exec rm -f {} +
	@find . -name "*~" -exec rm -f {} +
	@find . -name "__pycache__" -exec rm -rf {} +

.PHONY: clean-test
clean-test:
	@echo "Removing coverage data"
	@rm -f .coverage || true
	@rm -f .coverage.* || true
	@rm -rf htmlcov || true
	@rm -f junit.xml || true

.PHONY: clean
clean: clean-pyc clean-test

# ── Formatting ────────────────────────────────────────────────────────────────

.PHONY: format
format: format-python format-markdown

.PHONY: format-python
format-python:
	$(VENV) isort --settings-path pyproject.toml $(PYTHON_TARGETS)
	$(VENV) black $(PYTHON_TARGETS)
	$(VENV) ruff check --fix --quiet $(PYTHON_TARGETS)
	$(VENV) black $(PYTHON_TARGETS)

.PHONY: format-markdown
format-markdown:
	$(VENV) mdformat $(MARKDOWN_TARGETS)

.PHONY: format-check
format-check: format-check-python format-check-markdown

.PHONY: format-check-python
format-check-python:
	$(VENV) isort --settings-path pyproject.toml --check-only $(PYTHON_TARGETS)
	$(VENV) black --check $(PYTHON_TARGETS)
	$(VENV) ruff check --quiet $(PYTHON_TARGETS)

.PHONY: format-check-markdown
format-check-markdown:
	$(VENV) mdformat --check $(MARKDOWN_TARGETS)

# ── Linting ───────────────────────────────────────────────────────────────────

.PHONY: lint
lint: ruff-fix pylint

.PHONY: lint-check
lint-check: ruff-check pylint

.PHONY: ruff-fix
ruff-fix:
	$(VENV) ruff check --fix --quiet $(PYTHON_TARGETS)

.PHONY: ruff-check
ruff-check:
	$(VENV) ruff check --quiet $(PYTHON_TARGETS)

.PHONY: pylint
pylint:
	@echo "Linting with pylint"
	$(VENV) pylint $(PACKAGES) test --fail-under 9.8

# ── Metadata / version ───────────────────────────────────────────────────────

.PHONY: jiggle_version
jiggle_version:
ifeq ($(CI),true)
	@echo "Running in CI mode"
	jiggle_version check
else
	@echo "Running locally"
	jiggle_version hash-all
endif

.PHONY: metadata
metadata:
	$(VENV) metametameta pep621
	$(VENV) ./scripts/make_source.sh

.PHONY: metadata-check
metadata-check:
	$(VENV) metametameta sync-check

.PHONY: version-check
version-check:
	$(VENV) jiggle_version check

# ── Security ──────────────────────────────────────────────────────────────────

.PHONY: bandit
bandit:
	@echo "Security checks"
	$(VENV) bandit src -r --quiet

.PHONY: security
security: bandit

# ── Pre-commit ────────────────────────────────────────────────────────────────

.PHONY: pre-commit
pre-commit:
	@echo "Pre-commit checks"
	$(VENV) pre-commit run --all-files

# ── Type checking ─────────────────────────────────────────────────────────────

.PHONY: mypy
mypy:
	@echo "Running mypy on $(PACKAGES)"
	$(VENV) mypy $(PACKAGES) --ignore-missing-imports --check-untyped-defs

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: install_plugins
install_plugins:
	@echo "N/A"

.PHONY: test
test: clean sync install_plugins
	@echo "Running unit tests"
	$(VENV) pytest test -vv -n 2 --cov=src --cov-report=html --cov-fail-under 5 --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh

.PHONY: test-ci
test-ci: clean sync install_plugins
	@echo "Running unit tests (CI)"
	$(VENV) pytest test -q -n auto --dist=loadfile --cov=src --cov-report=xml --cov-fail-under 5 --cov-branch --junitxml=junit.xml --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh

# ── Dog-food / dev-status ─────────────────────────────────────────────────────

.PHONY: update_dev_status
update_dev_status:
	python -m troml_dev_status update .

.PHONY: dog_food
dog_food:
	troml-dev-status validate .
	metametameta sync-check

# ── Quality gates ─────────────────────────────────────────────────────────────

.PHONY: check
check: format-check lint-check security test mypy metadata-check version-check update_dev_status dog_food
	@echo "All checks passed."

.PHONY: check-ci
check-ci: format-check lint-check security test-ci mypy metadata-check version-check
	@echo "CI checks passed."

# ── Documentation ─────────────────────────────────────────────────────────────

.PHONY: check_docs
check_docs:
	$(VENV) interrogate src --verbose --fail-under 70
	$(VENV) pydoctest src --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"

.PHONY: make_docs
make_docs:
	@echo "Generating documentation for $(PACKAGES)"
	$(VENV) pdoc $(PACKAGES) --html -o docs --force

.PHONY: check_md
check_md:
	$(VENV) linkcheckMarkdown README.md
	$(VENV) markdownlint README.md --config .markdownlintrc
	$(VENV) mdformat --check $(MARKDOWN_TARGETS)

.PHONY: check_spelling
check_spelling:
	$(VENV) pylint $(PACKAGES) --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) pylint docs --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) codespell README.md --ignore-words=private_dictionary.txt
	$(VENV) codespell src --ignore-words=private_dictionary.txt
	$(VENV) codespell docs --ignore-words=private_dictionary.txt

.PHONY: check_changelog
check_changelog:
	$(VENV) changelogmanager validate

.PHONY: check_all_docs
check_all_docs: check_docs check_md check_spelling check_changelog

# ── Publishing ────────────────────────────────────────────────────────────────

.PHONY: publish
publish: test
	rm -rf dist && hatch build

# ── GitHub Actions maintenance ────────────────────────────────────────────────

.PHONY: issues
issues:
	@echo "N/A"

.PHONY: github-actions-upgrade
github-actions-upgrade:
	@echo "[github-actions-upgrade]"
	$(PINACT_RUN) -u
