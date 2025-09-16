#!/usr/bin/env bash
set -euo pipefail

troml_dev_status --help
troml_dev_status .
troml_dev_status . --json

