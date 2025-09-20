# troml_dev_status/cli.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from rich.console import Console

from troml_dev_status.analysis import filesystem
from troml_dev_status.engine import run_analysis
from troml_dev_status.reporting import print_human_report, print_json_report


def _require_git_repo(console: Console, repo_path: Path) -> bool:
    if not repo_path.is_dir() or not (repo_path / ".git").is_dir():
        console.print(f"Error: Path '{repo_path}' is not a valid Git repository.")
        return False
    return True


def _infer_project_name(console: Console, repo_path: Path) -> str | None:
    project_name = filesystem.get_project_name(repo_path)
    if not project_name:
        console.print(
            f"Error: Could not find [project].name in '{repo_path / 'pyproject.toml'}'."
        )
        return None
    return project_name


def cmd_analyze(args: argparse.Namespace, console: Console) -> int:
    repo_path: Path = args.repo_path.resolve()
    if not _require_git_repo(console, repo_path):
        return 1

    project_name = _infer_project_name(console, repo_path)
    if not project_name:
        return 1

    with console.status(f"Analyzing '{project_name}'..."):
        try:
            report = run_analysis(repo_path, project_name)
        except Exception as e:  # pragma: no cover (bubble for debugging)
            console.print(f"An unexpected error occurred during analysis: {e}")
            raise

    if args.json:
        print_json_report(report)
    else:
        print_human_report(report)

    return 0


def cmd_validate(args: argparse.Namespace, console: Console) -> int:
    """Exit non-zero if pyproject's Development Status classifier differs from inferred."""
    repo_path: Path = args.repo_path.resolve()
    if not _require_git_repo(console, repo_path):
        return 1

    project_name = _infer_project_name(console, repo_path)
    if not project_name:
        return 1

    with console.status(f"Analyzing '{project_name}' for validation..."):
        report = run_analysis(repo_path, project_name)

    inferred = report.inferred_classifier
    current = filesystem.get_dev_status_classifier(repo_path)

    if current is None:
        console.print(
            "[yellow]No Development Status trove classifier declared in pyproject.toml.[/yellow]"
        )
        console.print(f"Inferred: [bold cyan]{inferred}[/bold cyan]")
        return 2

    if current == inferred:
        console.print(
            f"[green]OK[/green] pyproject.toml matches inferred: [bold]{inferred}[/bold]."
        )
        return 0

    console.print("[red]Mismatch detected.[/red]")
    console.print(f"  Declared: [bold red]{current}[/bold red]")
    console.print(f"  Inferred: [bold green]{inferred}[/bold green]")
    if args.json:
        # Still useful to return the full analysis when machine-consuming
        print_json_report(report)
    return 2


def cmd_update(args: argparse.Namespace, console: Console) -> int:
    """Update pyproject.toml to the inferred Development Status classifier (in-place)."""
    repo_path: Path = args.repo_path.resolve()
    if not _require_git_repo(console, repo_path):
        return 1

    project_name = _infer_project_name(console, repo_path)
    if not project_name:
        return 1

    with console.status(f"Analyzing '{project_name}' before update..."):
        report = run_analysis(repo_path, project_name)

    inferred = report.inferred_classifier
    current = filesystem.get_dev_status_classifier(repo_path)

    if current == inferred:
        console.print(
            f"[green]No change needed[/green]; already set to [bold]{inferred}[/bold]."
        )
        return 0

    changed = filesystem.set_dev_status_classifier(repo_path, inferred)
    if not changed:
        console.print("[red]Failed to update pyproject.toml.[/red]")
        return 1

    console.print(
        f"Updated pyproject.toml Development Status: [red]{current or 'none'}[/red] → [green]{inferred}[/green]"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Infer PyPI Development Status from code and release artifacts (PEP XXXX)."
        )
    )

    sub = parser.add_subparsers(dest="command", required=False)

    # analyze (default) -----------------------------------------------------
    p_analyze = sub.add_parser(
        "analyze", help="Run analysis and print a human or JSON report"
    )
    p_analyze.add_argument("repo_path", type=Path, help="Path to the local Git repo")
    p_analyze.add_argument(
        "--json",
        action="store_true",
        help="Output the full evidence report in JSON format",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    # validate --------------------------------------------------------------
    p_validate = sub.add_parser(
        "validate",
        help=(
            "Exit non-zero if pyproject's Development Status classifier differs from inferred"
        ),
    )
    p_validate.add_argument("repo_path", type=Path, help="Path to the local Git repo")
    p_validate.add_argument(
        "--json",
        action="store_true",
        help="Also print the full evidence report as JSON on mismatch",
    )
    p_validate.set_defaults(func=cmd_validate)

    # update ----------------------------------------------------------------
    p_update = sub.add_parser(
        "update", help="Update pyproject.toml Development Status to the inferred value"
    )
    p_update.add_argument("repo_path", type=Path, help="Path to the local Git repo")
    p_update.set_defaults(func=cmd_update)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args()

    console = Console(stderr=True, style="bold red")

    # Default to `analyze` if no subcommand was given (preserve old behavior)
    if not getattr(args, "command", None):
        # Re-parse as analyze for backward compatibility
        sys.argv.insert(1, "analyze")
        args = parser.parse_args(args=argv)

    return args.func(args, console)


if __name__ == "__main__":
    sys.exit(main())
