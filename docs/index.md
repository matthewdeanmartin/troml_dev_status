# Welcome to troml-dev-status

** A tool to objectively infer PyPI "Development Status" classifiers from code and release artifacts.**

This project is inspired by `troml` and the need for objective criteria for Python project maturity. It provides a
deterministic, evidence-based method to suggest a `Development Status` classifier based on the rules outlined in
the [draft PEP](pep.md).

As far as I know, no python authority has given objective criteria for development status and the meaning is private to
each user. This tool aims to change that by providing a consistent, verifiable rubric.
  
### Guiding Principles

- ** In Scope:** Easily graded, objective metrics from Git history, source code, `pyproject.toml`, and PyPI release
  data.
- ** Out of Scope:** Vibes, intentions, promises, support contracts, budget, staffing, or any other subjective measure.
- ** Surprisingly Out of Scope:** Interface and API stability. This is nearly impossible to evaluate mechanically in
  Python and depends heavily on developer intent.

### Project Health

| Metric      | Status                                                                                                                                                                                                                |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Coverage    | [![codecov](https://codecov.io/gh/matthewdeanmartin/troml_dev_status/branch/main/graph/badge.svg)](https://codecov.io/gh/matthewdeanmartin/troml_dev_status)                                                          |
| Docs        | [![Docs](https://readthedocs.org/projects/troml_dev_status/badge/?version=latest)](https://troml_dev_status.readthedocs.io/en/latest/)                                                                                |
| PyPI        | [![PyPI](https://img.shields.io/pypi/v/troml_dev_status)](https://pypi.org/project/troml_dev_status/)                                                                                                                 |
| License     | [![License](https://img.shields.io/github/license/matthewdeanmartin/troml_dev_status)](https://github.com/matthewdeanmartin/troml_dev_status/blob/main/LICENSE)                                                       |
| Last Commit | ![Last Commit](https://img.shields.io/github/last-commit/matthewdeanmartin/troml_dev_status)                                                                                                                          |