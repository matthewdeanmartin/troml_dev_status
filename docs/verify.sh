#!/bin/bash
set -euo pipefail

echo
echo "Formatting markdown files with mdformat"
echo
uv run mdformat .

echo
echo "Checking documentation links and build"
echo
uv run mkdocs build --strict
