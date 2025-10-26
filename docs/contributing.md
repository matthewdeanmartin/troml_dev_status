## How Can I Contribute?

There are many ways to contribute, from writing code to improving documentation.

* **Reporting Bugs:** If you find a bug, please open an issue and provide as much detail as possible, including the
  repository you were analyzing and the output you received.
* **Suggesting Enhancements:** Have an idea for a new check or a better way to calculate the development status? Open an
  issue to start a discussion.
* **Pull Requests:** If you're ready to contribute code, this guide will walk you through the process. The most common
  contribution is adding a new check.

-----

## Development Setup

To get your local development environment set up, follow these steps:

1. **Fork and Clone:** Fork the repository on your Git platform and then clone it to your local machine.

2. **Create a Virtual Environment:** It's highly recommended to work inside a Python virtual environment.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   # On Windows, use: .venv\Scripts\activate
   ```

3. **Install Dependencies:** Install the project in editable mode along with its development dependencies.

   ```bash
   pip install -e ".[dev]"
   ```

4. **Run the Tests:** Before making any changes, ensure all existing tests pass.

   ```bash
   pytest
   ```

-----

## Architectural Overview

The core logic of the application is separated into a few key areas:

* `analysis/`: Modules that inspect the filesystem, Git history, PyPI data, etc. They **gather raw data** but do not
  make pass/fail judgments.
* `checks.py`, `checks_completeness.py`, `analysis/signs_of_bad.py`: These files contain the **check functions**. Each
  function implements a specific rule, analyzes data, and returns a `CheckResult` object (`passed`: bool, `evidence`:
  str).
* `engine.py`: This is the orchestrator. The `run_analysis` function calls all the check functions. The
  `determine_status` function uses the results of those checks to calculate the final "Development Status" classifier.
* `reporting.py`: This module takes the final `EvidenceReport` and formats it for display (e.g., as a table, JSON, or
  HTML).

-----

## Adding a New Check

This is the most common and impactful way to contribute. Adding a new check involves touching a few different files.
Here is a step-by-step guide.

Let's imagine we want to add a new "Quality" check with the ID **Q10** that checks for the presence of a `CITATION.cff`
file.

### 1\. Write the Analysis Logic (If Needed)

If your check needs new information from the repository that isn't already gathered, add a function to one of the
modules in `analysis/`. For our example, we need to find a `CITATION.cff` file. A good place for this would be in
`analysis/bureaucracy.py`.

*You would extend `analysis/bureaucracy.py` to recognize citation files.*

### 2\. Create the Check Function

Next, implement the function that returns a `CheckResult`. Since this is a "Quality" check, it belongs in `checks.py`.

```python
# In troml_dev_status/checks.py

from troml_dev_status.analysis.bureaucracy import get_bureaucracy_files
from troml_dev_status.models import CheckResult


# ... other check functions ...

def check_q10_citation_file_present(repo_path: Path) -> CheckResult:
    """Checks for the presence of a CITATION.cff or similar file."""
    citation_files = get_bureaucracy_files(repo_path, categories=["citation"])
    if citation_files:
        return CheckResult(
            passed=True,
            evidence=f"Found citation file: {citation_files[0].name}",
        )
    return CheckResult(
        passed=False,
        evidence="No CITATION.cff or similar file found.",
    )
```

### 3\. Wire the Check into the Engine

Now, you need to call your new function from `engine.py` so it actually runs.

```python
# In troml_dev_status/engine.py inside the run_analysis function

# ... imports ...
from troml_dev_status.checks import (
    # ... other checks ...
    check_q10_citation_file_present,  # 1. Import your new function
)


# ...

def run_analysis(repo_path: Path, project_name: str) -> EvidenceReport:
    # ...
    # Q-Checks (Quality)
    results["Q1"] = check_q1_ci_config_present(repo_path)
    # ... other Q checks ...
    results["Q9"] = check_q9_changelog_validates(repo_path)
    results["Q10"] = check_q10_citation_file_present(repo_path)  # 2. Call your function

    # ... rest of the function ...
```

### 4\. Add a Human-Readable Description

For the check to show up nicely in reports, add its description to the `CHECK_DESCRIPTIONS` dictionary in
`reporting.py`.

```python
# In troml_dev_status/reporting.py

CHECK_DESCRIPTIONS = {
    # ...
    "Q9": "Changelog validates",
    "Q10": "Citation File Present",  # Add your new description here
    "S1": "Declares dunder-all",
    # ...
}
```

### 5\. Add the Check to a Scoring "Family"

The final step is to make sure your check influences the final score. In `engine.py`, inside the `determine_status`
function, there are several sets (`eps_src`, `completeness_src`, etc.) that define which checks matter for which
development level.

Since our `Q10` check is a sign of a more complete and mature project, we should add it to the `eps_src` (Early Phase
Score) and `completeness_src` families.

```python
# In troml_dev_status/engine.py inside the determine_status function

# ...

# Early Phase Score (“EPS”) signals early readiness.
eps_src = {
    # ...
    "Q7",  # changelog
    "Q10",  # Our new citation check
    "S1",  # __all__ exports
    # ...
}

# Completeness signals “done-ness”
completeness_src = {
    # ...
    "Q7",  # change log
    "Q10",  # Our new citation check
    "R5",
    # ...
}
# ...
```

### 6\. Write a Test

Finally, add a unit test for your new check to ensure it works correctly and doesn't break in the future. Based on your
project's conventions, you would use `pytest`.

-----

## Submitting Your Changes

1. **Create a Branch:** Create a new branch for your changes.
   ```bash
   git checkout -b feature/add-citation-check
   ```
2. **Commit Your Changes:** Make your changes and commit them with a clear, descriptive message.
   ```
   feat: Add Q10 check for CITATION.cff file

   This commit introduces a new quality check (Q10) that verifies
   the presence of a citation file (e.g., CITATION.cff).

   The check has been added to the EPS and Completeness scoring
   families to influence the final rating.
   ```
3. **Push and Open a Pull Request:** Push your branch to your fork and open a pull request against the main repository.
   In the PR description, explain the what and why of your change and link to any relevant issues.
