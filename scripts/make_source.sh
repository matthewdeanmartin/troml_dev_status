#!/usr/bin/env bash
set -euo pipefail
git2md src/troml_dev_status \
  --ignore __init__.py __pycache__ \
  __about__.py logging_config.py py.typed utils \
  --output SOURCE.md

git2md src/completion_checker \
  --ignore __init__.py __pycache__ \
  __about__.py logging_config.py py.typed utils \
  --output SOURCE_COMPLETION_CHECKER.md

git2md src/readme_rater \
  --ignore __init__.py __pycache__ \
  __about__.py logging_config.py py.typed utils \
  --output SOURCE_README_RATER.md