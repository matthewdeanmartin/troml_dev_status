# troml_dev_status

Project inspired by troml to suggest a Development Status based solely on objective criteria.

A tool to objectively infer PyPI "Development Status" classifiers from code and release artifacts, based on the
[draft PEP ∞](https://github.com/matthewdeanmartin/troml_dev_status/blob/main/docs/PEP.md).

As far as I know, no python authority has given objective criteria for development status and the meaning is 
private to each user. Development status gets brief mention in PEP301.

Meanings

- Development Status :: 1 - Planning - Minimum score. All projects get at least Planning.
- Development Status :: 2 - Pre-Alpha - Few points awarded by grading rubric.
- Development Status :: 3 - Alpha - Many points awarded
- Development Status :: 4 - Beta - Even more points awarded
- Development Status :: 5 - Production/Stable - Perfect score
- Development Status :: 6 - Mature - Production and signs of upgrade help, e.g. Deprecation
- Development Status :: 7 - Inactive - Impossible to award. If you publish now, you are active.

In scope - easily graded metrics.

Out of scope - vibes, intentions, promises, support contracts, budget, staffing.

Also out of scope - linting, type annotations, code coverage in the sense of running third party tools at eval time.

Surprisingly out of scope - interface and API stability. Impossible to evaluate in Python (several noble attempts!),
depends on developer wishes, hopes, aspirations, vibes which require psychology tests, not build tools.

## Installation

Should be safe to pipx install so as to not mix your dependencies with the tool's

```bash
pipx install troml-dev-status
````

## Usage

Run the tool against a local Git repository that has a `pyproject.toml` file.

```bash
# just display info
troml-dev-status analyze /path/to/your/project 

# fails if tool disagrees with your current development status
troml-dev-status verify /path/to/your/project 

# updates pyproject.toml with current status
troml-dev-status update /path/to/your/project 
```

The tool will analyze the project's PyPI releases, Git history, and source code to produce an evidence-based "
Development Status" classifier.

## Output

The tool outputs a human-readable summary table and a machine-readable JSON report.

### Example Human-Readable Output

```text
                              Development Status Analysis for troml-dev-status                              
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID           ┃ Description                 ┃ Status ┃ Evidence                                           ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ C1           │ SECURITY.md Present         │   OK   │ Checked for security files                         │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C2           │ Trusted Publisher           │   OK   │ All files in most recent package are attested.     │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C3           │ Dependencies Pinned         │   X    │ Found 3 not strictly pinned somehow: textstat,     │
│              │                             │        │ llvm-diagnostics, semantic-version.                │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C4           │ Reproducible Dev Env        │   OK   │ Found uv lockfile ('uv.lock').                     │
...

Final Inferred Classifier: Development Status :: 4 - Beta
Reason: EPS=13/18; version 0.2.0 < 1.0.0; recent release; S3 holds.

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

| Metric      | Status                                                                                                                                                                                                                |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Coverage    | [![codecov](https://codecov.io/gh/matthewdeanmartin/troml_dev_status/branch/main/graph/badge.svg)](https://codecov.io/gh/matthewdeanmartin/troml_dev_status)                                                          |
| Docs        | [![Docs](https://troml-dev-status.readthedocs.org/projects/troml_dev_status/badge/?version=latest)](https://troml-dev-status.readthedocs.io/en/latest/)                                                                                |
| PyPI        | [![PyPI](https://img.shields.io/pypi/v/troml_dev_status)](https://pypi.org/project/troml_dev_status/)                                                                                                                 |
| Downloads   | [![Downloads](https://static.pepy.tech/personalized-badge/troml-dev-status?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/troml_dev_status) |
| License     | [![License](https://img.shields.io/github/license/matthewdeanmartin/troml_dev_status)](https://github.com/matthewdeanmartin/troml_dev_status/blob/main/LICENSE)                                                       |
| Last Commit | ![Last Commit](https://img.shields.io/github/last-commit/matthewdeanmartin/troml_dev_status)                                                                                                                          |

## Library info pages

- [troml_dev_status](https://libraries.io/pypi/troml_dev_status)

## Snyk Security Pages

- [troml_dev_status](https://security.snyk.io/package/pip/troml_dev_status)

## Prior Art

Autofill/Suggest
- [troml](https://pypi.org/project/troml/)
- [check-python-versions](https://pypi.org/project/check-python-versions/)

Validate
- [classifier-checker](https://pypi.org/project/classifier-checker/)
- [pyroma](https://pypi.org/project/pyroma/)

Raw Data
- [trove-classifiers](https://pypi.org/project/trove-classifiers/)
- [trove-classifiers-cli](https://pypi.org/project/trove-classifiers-cli/)

UI/Initialization
- [trove-setup](https://pypi.org/project/trove-setup/)

License Tracking
- [pip-licenses](https://github.com/raimon49/pip-licenses)

