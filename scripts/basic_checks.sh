#!/usr/bin/env bash
set -euo pipefail

troml_dev_status --help
troml_dev_status analyze .
troml_dev_status analyze . --json
troml_dev_status validate .