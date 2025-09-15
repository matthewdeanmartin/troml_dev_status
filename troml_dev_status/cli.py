# troml_dev_status/cli.py

import argparse
import sys
from pathlib import Path

from rich.console import Console

from troml_dev_status.analysis import filesystem
from troml_dev_status.engine import run_analysis
from troml_dev_status.reporting import print_human_report, print_json_report


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Infer PyPI Development Status from code and release artifacts (PEP XXXX)."
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to the local Git repository of the project.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the full evidence report in JSON format instead of a human-readable table.",
    )

    args = parser.parse_args()
    console = Console(stderr=True, style="bold red")

    repo_path: Path = args.repo_path.resolve()
    if not repo_path.is_dir() or not (repo_path / ".git").is_dir():
        console.print(f"Error: Path '{repo_path}' is not a valid Git repository.")
        return 1

    project_name = filesystem.get_project_name(repo_path)
    if not project_name:
        console.print(
            f"Error: Could not find [project].name in '{repo_path / 'pyproject.toml'}'."
        )
        return 1

    with console.status(f"Analyzing '{project_name}'..."):
        try:
            report = run_analysis(repo_path, project_name)
        except Exception as e:
            console.print(f"An unexpected error occurred during analysis: {e}")
            # For debugging, you might want to re-raise
            # raise
            return 1

    if args.json:
        print_json_report(report)
    else:
        print_human_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
