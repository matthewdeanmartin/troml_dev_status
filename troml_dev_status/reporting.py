# troml_dev_status/reporting.py
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
import tomlkit
from rich.console import Console
from rich.table import Table

from troml_dev_status.models import EvidenceReport

logger = logging.getLogger(__name__)

CHECK_DESCRIPTIONS = {
    "R1": "Published to PyPI",
    "R2": "Wheel + sdist Present",
    "R3": "PEP 440 Versioning",
    "R4": "Recent Release",
    "R5": "Python Version Declared",
    "R6": "Current Python Support",
    "Q1": "CI Config Present",
    "Q2": "Multi-Python CI",
    "Q3": "Tests Present",
    "Q4": "Test/Source Ratio",
    "Q5": "Shipped Type Hints",
    "Q6": "Docs Present",
    "Q7": "Changelog Present",
    "Q8": "README complete",
    "Q9": "Changelog validates",
    "S1": "Declares dunder-all",
    # "S2": "Stable SemVer API",
    # "S3": "Pre-1.0 API Churn",
    "D1": "Deprecation Policy Evidence",
    "C1": "SECURITY.md Present",
    "C2": "Trusted Publisher",
    "C3": "Dependencies Pinned",
    "C4": "Reproducible Dev Env",
    "M1": "Project Age",
    "M2": "Recent Code Motion",
    "Cmpl1": "TODO markers",
    "Cmpl2": "NotImplemented usage",
    "Cmpl3": "Placeholder `pass`",
    "Cmpl4": "Stub files",
    # Fail
    "Fail0": "Zero file count",
    "Fail1": "Tiny code base",
    "Fail2": "All emty files",
    "Fail3": "Only Empty init",
    "Fail4": "No Package init",
    "Fail5": "Python fails to parse",
    "Fail6": ".py isn't python",
    "Fail7": "High stub density",
    "Fail8": "Not importable",
    "Fail9": "Possible parked name",
    "Fail10": "Bad metadata",
    "Fail11": "Pointless content",
    "Fail12": "Dependencies not imported",
}

# ---------------- existing JSON + human table ----------------


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
        status_icon = (
            "[bold green]OK[/bold green]" if result.passed else "[bold red]X[/bold red]"
        )
        base_check_id = check_id_full.split(" ")[0]
        description = CHECK_DESCRIPTIONS.get(base_check_id, "Unknown Check")

        table.add_row(check_id_full, description, status_icon, result.evidence)

    console.print(table)
    console.print(
        f"\n[bold]Final Inferred Classifier:[/] [green]{report.inferred_classifier}[/green]"
    )
    console.print(f"[bold]Reason:[/] {report.reason}")


# ---------------- shared helpers ----------------


def _checks_as_rows(report: EvidenceReport) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for check_id_full in sorted(report.checks.keys()):
        result = report.checks[check_id_full]
        base_check_id = check_id_full.split(" ")[0]
        rows.append(
            {
                "id": check_id_full,
                "base_id": base_check_id,
                "description": CHECK_DESCRIPTIONS.get(base_check_id, "Unknown Check"),
                "passed": bool(result.passed),
                "evidence": result.evidence,
            }
        )
    return rows


def _write_or_stdout(text: str, to_path: Optional[Path] = None) -> None:
    if to_path:
        Path(to_path).parent.mkdir(parents=True, exist_ok=True)
        Path(to_path).write_text(text, encoding="utf-8")
    else:
        print(text)


# ---------------- #1 SIMPLE TEXT (fixed-width) ----------------


def render_simple(
    report: EvidenceReport,
    to_path: Path | None = None,
    width_id: int = 12,
    width_desc: int = 28,
    width_status: int = 6,
) -> None:
    """
    A no-frills, fixed-width renderer that avoids box-drawing chars and emojis.
    """
    rows = _checks_as_rows(report)
    # header
    lines: List[str] = []
    title = f"Development Status Analysis — {report.project_name}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append(
        f"{'ID'.ljust(width_id)} {'Description'.ljust(width_desc)} {'Status'.ljust(width_status)} Evidence"
    )
    lines.append("-" * (width_id + 1 + width_desc + 1 + width_status + 1 + 8))

    for r in rows:
        status = "OK" if r["passed"] else "X"
        lines.append(
            f"{r['id'][:width_id].ljust(width_id)} "
            f"{r['description'][:width_desc].ljust(width_desc)} "
            f"{status.ljust(width_status)} "
            f"{r['evidence']}"
        )

    lines.append("")
    lines.append(f"Final Inferred Classifier: {report.inferred_classifier}")
    lines.append(f"Reason: {report.reason}")

    _write_or_stdout("\n".join(lines), to_path)


# ---------------- #2 HTML via Jinja2 ----------------

_DEFAULT_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ project_name }} — Dev Status Report</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  {% if inline_css %}
  <style>
    :root { --ok:#0a7a12; --bad:#b00020; --muted:#666; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial, sans-serif;
           margin: 2rem; line-height: 1.45; }
    h1 { margin-bottom: 0.2rem; }
    .muted { color: var(--muted); }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { padding: .5rem .6rem; border-bottom: 1px solid #eee; vertical-align: top; }
    th { text-align: left; font-weight: 600; }
    .status-ok { color: var(--ok); font-weight: 700; }
    .status-bad { color: var(--bad); font-weight: 700; }
    .chip { display:inline-block; padding:.15rem .45rem; border-radius:.45rem; background:#f5f5f5; }
    .meta { margin-top: 1rem; }
    .reason { margin-top: 0.75rem; white-space: pre-wrap; }
  </style>
  {% endif %}
</head>
<body>
  <h1>Development Status — {{ project_name }}</h1>
  <div class="meta muted">Classifier: <span class="chip">{{ inferred_classifier }}</span></div>
  <div class="reason"><strong>Reason:</strong> {{ reason }}</div>

  <table>
    <thead>
      <tr><th>ID</th><th>Description</th><th>Status</th><th>Evidence</th></tr>
    </thead>
    <tbody>
    {% for r in rows %}
      <tr>
        <td><code>{{ r.id }}</code></td>
        <td>{{ r.description }}</td>
        <td class="{{ 'status-ok' if r.passed else 'status-bad' }}">{{ 'OK' if r.passed else 'X' }}</td>
        <td class="muted">{{ r.evidence }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""


def render_html(
    report: EvidenceReport,
    to_path: Path | None = None,
    template: str | None = None,
    inline_css: bool = True,
) -> None:
    """
    Render HTML using Jinja2; writes to file if to_path given, else stdout.
    """
    if jinja2 is None:
        raise RuntimeError("jinja2 is required for HTML output. `pip install jinja2`")
    env = jinja2.Environment(autoescape=True)
    tmpl = env.from_string(template or _DEFAULT_HTML_TEMPLATE)
    html = tmpl.render(
        project_name=report.project_name,
        inferred_classifier=report.inferred_classifier,
        reason=report.reason,
        rows=_checks_as_rows(report),
        inline_css=inline_css,
    )
    _write_or_stdout(html, to_path)


# ---------------- #3 TOML via tomlkit ----------------


def render_toml(report: EvidenceReport, to_path: Path | None = None) -> None:
    """
    Emit a TOML document summarizing the report.
    """
    if tomlkit is None:
        raise RuntimeError("tomlkit is required for TOML output. `pip install tomlkit`")

    doc = tomlkit.document()
    doc.add("project_name", report.project_name)  # type: ignore[arg-type]
    doc.add("inferred_classifier", report.inferred_classifier)  # type: ignore[arg-type]
    doc.add("reason", report.reason)  # type: ignore[arg-type]

    checks_table = tomlkit.table()
    for r in _checks_as_rows(report):
        entry = tomlkit.table()
        entry.add("description", r["description"])
        entry.add("passed", r["passed"])
        entry.add("evidence", r["evidence"])
        checks_table.add(r["id"], entry)
    doc.add("checks", checks_table)

    toml_text = tomlkit.dumps(doc)
    _write_or_stdout(toml_text, to_path)


# ---------------- #4 VT100 (color/bold/italic), no tables ----------------

CSI = "\x1b["
RESET = CSI + "0m"
BOLD = CSI + "1m"
ITALIC = CSI + "3m"
FG_GREEN = CSI + "32m"
FG_RED = CSI + "31m"
FG_CYAN = CSI + "36m"
FG_DIM = CSI + "2m"


def render_vt100(
    report: EvidenceReport, to_path: Path | None = None, use_color: bool = True
) -> None:
    """
    Stream friendly: plain lines with ANSI colors and basic emphasis. No tables.
    """

    def c(s: str, code: str) -> str:
        return f"{code}{s}{RESET}" if use_color else s

    lines: List[str] = []
    title = f"Development Status — {report.project_name}"
    lines.append(c(title, BOLD + FG_CYAN))
    lines.append("-" * len(title))
    lines.append(f"{c('Classifier:', BOLD)} {report.inferred_classifier}")
    lines.append(f"{c('Reason:', BOLD)} {report.reason}")
    lines.append("")

    for r in _checks_as_rows(report):
        status = c("OK", FG_GREEN + BOLD) if r["passed"] else c("X", FG_RED + BOLD)
        header = f"{c(r['id'], BOLD)} {c(r['description'], ITALIC)} — {status}"
        lines.append(header)
        if r["evidence"]:
            lines.append("  " + c(r["evidence"], FG_DIM))
        lines.append("")

    _write_or_stdout("\n".join(lines), to_path)


# ---------------- #5 Markdown via Jinja2 ----------------

_DEFAULT_MD_TEMPLATE = """# Development Status — {{ project_name }}

**Classifier:** `{{ inferred_classifier }}`

**Reason:** {{ reason }}

## Checks

| ID | Description | Status | Evidence |
|---:|:------------|:------:|:---------|
{% for r in rows -%}
| `{{ r.id }}` | {{ r.description }} | {{ '✅' if r.passed else '❌' }} | {{ r.evidence | replace('\n', '<br>') }} |
{% endfor %}
"""


def render_markdown(
    report: EvidenceReport,
    to_path: Path | None = None,
    template: str | None = None,
) -> None:
    """
    Render Markdown via Jinja2; writes to file if to_path given, else stdout.
    """
    env = jinja2.Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    tmpl = env.from_string(template or _DEFAULT_MD_TEMPLATE)
    md = tmpl.render(
        project_name=report.project_name,
        inferred_classifier=report.inferred_classifier,
        reason=report.reason,
        rows=_checks_as_rows(report),
    )
    _write_or_stdout(md, to_path)


# ---------------- dispatcher ----------------


def render_report(report: EvidenceReport, fmt: str, **kwargs) -> None:
    """
    Dispatch to a renderer.
    fmt in {"simple", "html", "toml", "vt100", "md", "markdown", "json", "rich"}
    """
    fmt = fmt.lower()
    if fmt in {"json"}:
        return print_json_report(report)
    if fmt in {"rich", "human", "table"}:
        return print_human_report(report)
    if fmt == "simple":
        return render_simple(report, **kwargs)
    if fmt == "html":
        return render_html(report, **kwargs)
    if fmt == "toml":
        return render_toml(report, **kwargs)
    if fmt in {"vt100", "ansi"}:
        return render_vt100(report, **kwargs)
    if fmt in {"md", "markdown"}:
        return render_markdown(report, **kwargs)
    raise ValueError(f"Unknown format: {fmt}")
