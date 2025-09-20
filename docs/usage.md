# Command-Line Usage

Run the tool against a local Git repository that contains a `pyproject.toml` file.

### `analyze`

Analyzes the project and prints a human-readable report to the console.

```bash
troml-dev-status analyze /path/to/your/project
```

You can also output the full results as a machine-readable JSON object.

```Bash
troml-dev-status analyze /path/to/your/project --json
```

## validate

Analyzes the project and exits with a non-zero status code if the inferred classifier disagrees with the one currently
set in your pyproject.toml. This is useful for CI/CD pipelines.

```bash
troml-dev-status validate /path/to/your/project
```

## update

Analyzes the project and automatically updates the Development Status classifier in your pyproject.toml file to the
inferred value.

```bash
troml-dev-status update /path/to/your/project
```

## Example Output

### Human-Readable Table

The default output is a summary table showing the status of each check.

```plaintext

                              Development Status Analysis for troml-dev-status
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID           ┃ Description                 ┃ Status ┃ Evidence                                           ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ C1           │ SECURITY.md Present         │   OK   │ Checked for security files                         │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C2           │ Trusted Publisher           │   OK   │ All files in most recent package are attested.     │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
...

Final Inferred Classifier: Development Status :: 4 - Beta
Reason: EPS=13/18; version 0.2.0 < 1.0.0; recent release; S3 holds.
```

## JSON Report

Using the --json flag produces a detailed report suitable for automation.

```JSON
{
  "inferred_classifier": "Development Status :: 4 - Beta",
  "reason": "EPS=13/18; version 0.2.0 < 1.0.0; recent release; S3 holds.",
  "project_name": "troml-dev-status",
  "evaluated_at": "2025-09-20T17:00:00.123Z",
  "checks": {
    "R1": {
      "passed": true,
      "evidence": "Found 2 releases on PyPI for 'troml-dev-status'"
    },
    "R2": {
      "passed": true,
      "evidence": "Latest release 0.2.0 has wheel and sdist"
    }
  },
  "metrics": {
    "eps_score": 13,
    "eps_total": 18
  }
}
```