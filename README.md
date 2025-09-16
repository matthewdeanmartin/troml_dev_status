# troml_dev_status
Project inspired by troml to suggest a Development Status based solely on objective criteria.

A tool to objectively infer PyPI "Development Status" classifiers from code and release artifacts, based on the 
[draft PEP ∞](docs/PEP.md).

## Installation

```bash
pip install troml-dev-status
````

## Usage

Run the tool against a local Git repository that has a `pyproject.toml` file.

```bash
troml-dev-status /path/to/your/project
```

The tool will analyze the project's PyPI releases, Git history, and source code to produce an evidence-based "Development Status" classifier.

## Output

The tool outputs a human-readable summary table and a machine-readable JSON report.

### Example Human-Readable Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check ID                         ┃ Status ┃ Evidence                                    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ R1. Published at least once      │   ✅   │ Found 15 releases on PyPI for 'my-package'  │
│ R2. Wheel + sdist present        │   ✅   │ Latest release 1.2.3 has wheel and sdist    │
│ ...                              │   ...  │ ...                                         │
│ Q5. Type hints shipped           │   ❌   │ 45.8% of 120 public symbols are annotated   │
│ ...                              │   ...  │ ...                                         │
└──────────────────────────────────┴────────┴─────────────────────────────────────────────┘
          Final Inferred Classifier: Development Status :: 4 - Beta
 Reason: EPS=16/19; version 0.8.0 < 1.0.0; recent release (35 days ago)
```

### Example JSON Output

The tool also prints a detailed JSON object containing the results of every check.

```json
{
  "inferred_classifier": "Development Status :: 4 - Beta",
  "evaluated_at": "2025-09-14T20:00:00.123456Z",
  "checks": {
    "R1": {
      "passed": true,
      "evidence": "Found 15 releases on PyPI for 'my-package'"
    },
    "...": {}
  },
  "metrics": {
    "eps_score": 16,
    "eps_total": 19
  }
}
```

## Project Health

| Metric         | Status |
|----------------|--------|
| Coverage       | [![codecov](https://codecov.io/gh/matthewdeanmartin/troml_dev_status/branch/main/graph/badge.svg)](https://codecov.io/gh/matthewdeanmartin/troml_dev_status) |
| Docs           | [![Docs](https://readthedocs.org/projects/troml_dev_status/badge/?version=latest)](https://troml_dev_status.readthedocs.io/en/latest/) |
| PyPI           | [![PyPI](https://img.shields.io/pypi/v/troml_dev_status)](https://pypi.org/project/troml_dev_status/) |
| Downloads      | [![Downloads](https://static.pepy.tech/personalized-badge/troml_dev_status?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/troml_dev_status) |
| License        | [![License](https://img.shields.io/github/license/matthewdeanmartin/troml_dev_status)](https://github.com/matthewdeanmartin/troml_dev_status/blob/main/LICENSE.md) |
| Last Commit    | ![Last Commit](https://img.shields.io/github/last-commit/matthewdeanmartin/troml_dev_status) |

## Libray info pages
- [troml_dev_status](https://libraries.io/pypi/troml_dev_status)

## Snyk Security Pages

- [troml_dev_status](https://security.snyk.io/package/pip/troml_dev_status)