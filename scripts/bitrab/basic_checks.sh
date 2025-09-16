#! /bin/bash
set -eou pipefail
# Smoke test  all the tests that don't necessarily change anything
# exercises the arg parser mostly.
set -eou pipefail
echo "help..."
troml_dev_status --help
echo "compile help..."
troml_dev_status run --help
echo "version..."
troml_dev_status --version
echo "dry run run"
troml_dev_status run --dry-run
echo "done"

