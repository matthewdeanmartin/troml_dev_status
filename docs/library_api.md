# Using as a Library

In addition to the command-line interface, you can use `troml-dev-status` as a Python library to integrate its analysis
into other tools.

The primary entry point is the `run_analysis` function.

### Example

Here is a basic example of how to run an analysis programmatically:

```python
from pathlib import Path
from troml_dev_status import run_analysis

# Define the path to your local Git repository
repo_path = Path("/path/to/your/project")

# The project name must match what's on PyPI
project_name = "your-pypi-project-name"

try:
    # Run the full analysis
    report = run_analysis(repo_path, project_name)

    # Print the inferred classifier and the reason
    print(f"Inferred Classifier: {report.inferred_classifier}")
    print(f"Reason: {report.reason}")

    # Access detailed check results
    if not report.checks["C4"].passed:
        print(f"Check C4 (Repro Inputs) failed: {report.checks['C4'].evidence}")

except Exception as e:
    print(f"An error occurred: {e}")
```

## The EvidenceReport Object

The run_analysis function returns an EvidenceReport Pydantic model, which contains the full results. Key attributes
include:

- inferred_classifier (str): The final determined classifier string.

- reason (str): A human-readable explanation for the result.

- checks (dict): A dictionary where keys are check IDs (e.g., "R1", "Q4") and values are CheckResult objects containing
  a passed (bool) and evidence (str).

- metrics (Metrics): An object containing numerical data like the eps_score.