# troml_dev_status/__init__.py
"""
troml-dev-status: Infer PyPI Development Status from repository and release artifacts.

This package provides a library and command-line tool to objectively determine a
Python project's PEP 301 Development Status classifier based on a series of
automated checks against its code, configuration, and release history.

As far as I know, no python authority has given objective criteria for development status and the meaning is
private to each user.

The primary public API includes:

- run_analysis: The main entry point to perform a full analysis on a project.
- EvidenceReport, CheckResult, Metrics: Pydantic models defining the structure
  of the analysis results, useful for programmatic consumption.
- ChangelogValidator: A standalone utility to validate a changelog string against
  the Keep a Changelog standard.
- evaluate_readme, RubricResult: A standalone utility to score a README file's
  completeness based on a detailed rubric.
"""
from __future__ import annotations

from .analysis.readme_eval import RubricResult, evaluate_readme
from .analysis.validate_changelog import ChangelogValidator
from .engine import run_analysis
from .models import CheckResult, EvidenceReport, Metrics

__all__ = [
    # Core analysis engine
    "run_analysis",
    # Data models for results
    "EvidenceReport",
    "CheckResult",
    "Metrics",
    # Standalone utilities
    "ChangelogValidator",
    "evaluate_readme",
    "RubricResult",
]
