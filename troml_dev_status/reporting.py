# troml_dev_status/reporting.py
from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from troml_dev_status.models import EvidenceReport

CHECK_DESCRIPTIONS = {
    "R1": "Published to PyPI",
    "R2": "Wheel + sdist Present",
    "R3": "PEP 440 Versioning",
    "R4": "Recent Release",
    "R5": "Python Version Declared",
    "R6": "Current Python Support",
    "R7": "Healthy Distribution",
    "Q1": "CI Config Present",
    "Q2": "Multi-Python CI",
    "Q3": "Tests Present",
    "Q4": "Test/Source Ratio",
    "Q5": "Shipped Type Hints",
    "Q6": "Docs Present",
    "Q7": "Changelog Present",
    "S1": "No Silent API Removals",
    "S2": "Stable SemVer API",
    "S3": "Pre-1.0 API Churn",
    "D1": "Deprecation Policy Evidence",
    "C1": "SECURITY.md Present",
    "C2": "Signed Release Tags",
    "C3": "Dependencies Pinned",
    "C4": "Reproducible Dev Env",
    "M1": "Project Age",
    "M2": "Recent Code Motion",
}


def default_json_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def print_json_report(report: EvidenceReport):
    """Prints the full report as a JSON object."""
    console = Console()
    report_dict = report.model_dump()
    console.print(json.dumps(report_dict, indent=2, default=default_json_serializer))


def print_human_report(report: EvidenceReport):
    """Prints a human-readable summary table of the checks."""
    console = Console()

    table = Table(
        title=f"Development Status Analysis for [bold cyan]{report.project_name}[/bold cyan]",
        show_lines=True,
    )
    table.add_column("ID", style="bold white", width=12)
    table.add_column("Description", style="cyan", max_width=28)
    table.add_column("Status", justify="center")
    table.add_column("Evidence", style="dim", max_width=50)

    check_order = sorted(report.checks.keys())

    for check_id_full in check_order:
        result = report.checks[check_id_full]
        status_icon = "✅" if result.passed else "❌"

        # Get the base ID (e.g., 'R4' from 'R4 (12mo)') for the description lookup
        base_check_id = check_id_full.split(" ")[0]
        description = CHECK_DESCRIPTIONS.get(base_check_id, "Unknown Check")

        table.add_row(check_id_full, description, status_icon, result.evidence)

    console.print(table)
    console.print(
        f"\n[bold]Final Inferred Classifier:[/] [green]{report.inferred_classifier}[/green]"
    )
    console.print(f"[bold]Reason:[/] {report.reason}")
