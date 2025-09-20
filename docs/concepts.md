# Core Concepts & Philosophy

This page explains the motivation and scope of the `troml-dev-status` project, based on its founding PEP.

## Abstract

The tool defines an **objective** method to **infer** one of the canonical PyPI `Development Status` classifiers for a
Python project **exclusively from code, version control history, and published release artifacts**—with **no reliance on
maintainer statements, intentions, or “vibes.”**

The rubric is deterministic, based on verifiable checks. It treats early development phases as a series of checkboxes,
“Production/Stable” as a measure of product maturity, and “Mature” as time-tested production.

## Motivation

Trove development-status classifiers are self-declared and often ambiguous. Teams, users, and automated systems benefit
from an **evidence-based, reproducible** inference that:

* Works **only** from code and published artifacts.
* Is **independent** of maintainers’ subjective claims or current life situation.
* Yields a classifier that **matches measurable software maturity**.

## Scope & Non-Goals

* **In scope:** Rules that derive a status from Git history, tags, diffs, static analysis of code/docs/config, and *
  *PyPI releases**.

* **Out of scope:** Popularity metrics (stars/forks), issue triage rates, discussion forums, subjective code quality, or
  running tests in CI. We may **discover** tests exist; we do **not** need to *execute* them.

