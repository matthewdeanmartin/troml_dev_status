# troml_dev_status/engine.py
# Note: This is a simplified engine. A real implementation would be more robust.
# Many checks from the PEP are stubbed as 'not implemented' for this example.
from __future__ import annotations

from pathlib import Path
from typing import Dict

from troml_dev_status.analysis import filesystem, pypi
from troml_dev_status.analysis.bureaucracy import get_bureaucracy_files
from troml_dev_status.checks import (
    check_c3_minimal_pin_sanity,
    check_m1_project_age,
    check_m2_code_motion,
    check_q1_ci_config_present,
    check_q3_tests_present,
    check_q4_test_file_ratio,
    check_q5_type_hints_shipped,
    check_q6_docs_present,
    check_r1_published_at_least_once,
    check_r2_wheel_sdist_present,
    check_r4_recent_activity,
)
from troml_dev_status.models import CheckResult, EvidenceReport, Metrics


def run_analysis(repo_path: Path, project_name: str) -> EvidenceReport:
    """Orchestrates the analysis and classification process."""

    # --- Analysis Phase ---
    pypi_data = pypi.get_project_data(project_name)
    sorted_versions = pypi.get_sorted_versions(pypi_data) if pypi_data else []
    latest_version = sorted_versions[0] if sorted_versions else None
    analysis_mode = filesystem.get_analysis_mode(repo_path)

    # --- Checks Execution Phase ---
    results: Dict[str, CheckResult] = {}
    metrics = Metrics()

    # R-Checks (Release & Packaging)
    results["R1"] = check_r1_published_at_least_once(pypi_data)
    if latest_version:
        results["R2"] = check_r2_wheel_sdist_present(pypi_data or {}, latest_version)
        results["R4 (12mo)"] = check_r4_recent_activity(
            pypi_data or {}, latest_version, months=12
        )
    # Stubs for other R checks
    results["R3"] = CheckResult(passed=False, evidence="Not implemented.")
    results["R5"] = CheckResult(passed=False, evidence="Not implemented.")
    results["R6"] = CheckResult(passed=False, evidence="Not implemented.")
    results["R7"] = CheckResult(passed=False, evidence="Not implemented.")

    # Q-Checks (Quality)
    results["Q1"] = check_q1_ci_config_present(repo_path)
    results["Q2"] = CheckResult(
        passed=filesystem.has_multi_python_in_ci(
            filesystem.get_ci_config_files(repo_path)
        ),
        evidence="Simple check for multiple python versions in CI files.",
    )
    results["Q3"] = check_q3_tests_present(repo_path)
    results["Q4"] = check_q4_test_file_ratio(repo_path)
    results["Q5"], metrics.type_annotation_coverage, metrics.public_symbols_latest = (
        check_q5_type_hints_shipped(repo_path)
    )
    results["Q6"], metrics.readme_word_count = check_q6_docs_present(repo_path)
    results["Q7"] = CheckResult(
        passed=(repo_path / "CHANGELOG.md").exists(),
        evidence="Checked for CHANGELOG.md",
    )

    # S, D, C Checks (Stubs)
    results["S1"] = CheckResult(passed=False, evidence="Not implemented.")
    results["S2"] = CheckResult(passed=False, evidence="Not implemented.")
    results["S3"] = CheckResult(passed=False, evidence="Not implemented.")
    results["D1"] = CheckResult(passed=False, evidence="Not implemented.")
    results["C1"] = CheckResult(
        passed=len(get_bureaucracy_files(repo_path, categories=["security"])) >= 1,
        evidence="Checked for security files",
    )
    results["C2"] = CheckResult(passed=False, evidence="Not implemented.")
    results["C3"] = check_c3_minimal_pin_sanity(repo_path, analysis_mode)
    results["C4"] = CheckResult(passed=False, evidence="Not implemented.")

    # M-Checks (Maintenance)
    if pypi_data:
        results["M1"] = check_m1_project_age(pypi_data)
    results["M2 (12mo)"] = check_m2_code_motion(repo_path, months=12)

    # --- Classification Logic ---
    classifier, reason = determine_status(results, latest_version, metrics)

    return EvidenceReport(
        inferred_classifier=classifier,
        reason=reason,
        project_name=project_name,
        checks=results,
        metrics=metrics,
    )


def determine_status(
    results: Dict[str, CheckResult], latest_version, metrics: Metrics
) -> tuple[str, str]:
    """Applies the PEP's waterfall logic to determine the classifier."""

    # Unclassifiable
    if not results.get("R1", CheckResult(passed=False, evidence="")).passed:
        return "Development Status :: 1 - Planning", "Project has no releases on PyPI."

    # NOTE: Inactive, Production, Mature checks are simplified for this sketch.
    # A full implementation would be much more detailed.

    # Early-Phase Score (EPS)
    eps_set = {
        "R2",
        "R3",
        "R5",
        "R6",
        "R7",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "Q5",
        "Q6",
        "Q7",
        "S1",
        "S3",
        "D1",
        "C1",
        "C3",
        "C4",
        "M1",
    }
    eps_total = len(eps_set)
    eps_score = sum(
        1
        for check_id, result in results.items()
        if check_id in eps_set and result.passed
    )
    metrics.eps_score = eps_score
    metrics.eps_total = eps_total

    is_beta_candidate = (
        eps_score >= 12
        and latest_version.major == 0
        and results.get(
            "S3", CheckResult(passed=True, evidence="")
        ).passed  # Assuming S3 passes for now
        and results.get("R4 (12mo)", CheckResult(passed=False, evidence="")).passed
    )

    if is_beta_candidate:
        reason = f"EPS={eps_score}/{eps_total}; version {latest_version} < 1.0.0; recent release; S3 holds."
        return "Development Status :: 4 - Beta", reason

    if eps_score >= 7 and latest_version.major == 0:
        return (
            "Development Status :: 3 - Alpha",
            f"EPS={eps_score}/{eps_total}; version {latest_version} < 1.0.0.",
        )

    if eps_score >= 4 and latest_version.minor == 0:
        return (
            "Development Status :: 2 - Pre-Alpha",
            f"EPS={eps_score}/{eps_total}; version {latest_version} < 0.1.0.",
        )

    if eps_score >= 0 and latest_version.minor == 0:
        return (
            "Development Status :: 1 - Planning",
            f"EPS={eps_score}/{eps_total}; version {latest_version} < 0.1.0.",
        )

    return "Unknown", "Could not map to a development status based on checks."
