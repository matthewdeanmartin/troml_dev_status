# troml_dev_status/engine.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from troml_dev_status.analysis import filesystem, pypi
from troml_dev_status.analysis.bureaucracy import get_bureaucracy_files
from troml_dev_status.analysis.signs_of_bad import (
    check_ds0_zero_file_count,
    check_ds1_tiny_codebase,
    check_ds2_all_empty_files,
    check_ds3_only_empty_init,
    check_ds4_missing_package_init,
    check_ds5_unparsable_python,
    check_ds6_py_extension_nonpython,
    check_ds7_stubware_density,
    check_ds8_no_importable_modules,
    check_ds9_name_parking_signals,
    check_ds10_bad_metadata_pyproject,
    check_ds11_pointless_content,
    check_ds12_declares_deps_but_never_imports,
)
from troml_dev_status.checks import (
    check_c2_code_attestations,
    check_c3_minimal_pin_sanity,
    check_c4_repro_inputs,
    check_m1_project_age,
    check_m2_code_motion,
    check_q1_ci_config_present,
    check_q3_tests_present,
    check_q4_test_file_ratio,
    check_q5_type_hints_shipped,
    check_q6_docs_present,
    check_q8_readme_complete,
    check_q9_changelog_validates,
    check_r1_published_at_least_once,
    check_r2_wheel_sdist_present,
    check_r3_pep440_versioning,
    check_r4_recent_activity,
    check_r5_python_version_declaration,
    check_r6_current_python_coverage,
    check_s1_all_exports,
)
from troml_dev_status.checks_completeness import (
    check_cmpl1_todo_density,
    check_cmpl2_notimplemented_ratio,
    check_cmpl3_placeholder_pass_ratio,
    check_cmpl4_stub_files_ratio,
)
from troml_dev_status.models import CheckResult, EvidenceReport, Metrics

logger = logging.getLogger(__name__)


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
    results["R3"] = check_r3_pep440_versioning(pypi_data)
    results["R5"] = check_r5_python_version_declaration(repo_path, pypi_data)
    results["R6"] = check_r6_current_python_coverage(pypi_data or {})

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

    results["Q8"] = check_q8_readme_complete(repo_path)

    results["Q9"] = check_q9_changelog_validates(repo_path)

    # S, D, C Checks (Stubs)
    results["S1"] = check_s1_all_exports(repo_path)
    # results["S2"] = CheckResult(passed=False, evidence="Not implemented.")
    # results["S3"] = CheckResult(passed=False, evidence="Not implemented.")
    results["D1"] = CheckResult(passed=False, evidence="Not implemented.")
    results["C1"] = CheckResult(
        passed=len(get_bureaucracy_files(repo_path, categories=["security"])) >= 1,
        evidence="Checked for security files",
    )
    results["C2"] = check_c2_code_attestations(project_name)
    results["C3"] = check_c3_minimal_pin_sanity(repo_path, analysis_mode)
    results["C4"] = check_c4_repro_inputs(repo_path)

    # M-Checks (Maintenance)
    if pypi_data:
        results["M1"] = check_m1_project_age(pypi_data)
    results["M2 (12mo)"] = check_m2_code_motion(repo_path, months=12)

    results["Cmpl1"] = check_cmpl1_todo_density(repo_path)
    results["Cmpl2"] = check_cmpl2_notimplemented_ratio(repo_path)
    results["Cmpl3"] = check_cmpl3_placeholder_pass_ratio(repo_path)
    results["Cmpl4"] = check_cmpl4_stub_files_ratio(repo_path)

    results["Fail0"] = check_ds0_zero_file_count(repo_path)
    results["Fail1"] = check_ds1_tiny_codebase(repo_path)
    results["Fail2"] = check_ds2_all_empty_files(repo_path)
    results["Fail3"] = check_ds3_only_empty_init(repo_path)
    results["Fail4"] = check_ds4_missing_package_init(repo_path)
    results["Fail5"] = check_ds5_unparsable_python(repo_path)
    results["Fail6"] = check_ds6_py_extension_nonpython(repo_path)
    results["Fail7"] = check_ds7_stubware_density(repo_path)
    results["Fail8"] = check_ds8_no_importable_modules(repo_path)
    results["Fail9"] = check_ds9_name_parking_signals(pypi_data)  # requires pypi_data
    results["Fail10"] = check_ds10_bad_metadata_pyproject(repo_path)
    results["Fail11"] = check_ds11_pointless_content(repo_path)
    results["Fail12"] = check_ds12_declares_deps_but_never_imports(repo_path)

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

    is_bad = {
        "Fail0",
        "Fail1",
        "Fail2",
        "Fail3",
        "Fail4",
        "Fail5",
        "Fail6",
        "Fail7",
        "Fail8",
        "Fail9",
        "Fail10",
        "Fail11",
        "Fail12",
    }

    is_bad_total = len(is_bad)
    is_bad_score = sum(
        1
        for check_id, result in results.items()
        if check_id in is_bad and result.passed
    )

    # Early-Phase Score (EPS)
    eps_set = {
        "R2",  # wheels, sdist
        "R3",  # pep 440
        "R5",  # declare python
        "R6",  # support current, changes over time!
        "Q1",  # ci
        "Q2",  # multi python
        "Q3",  # tests
        "Q4",  # test ratio
        "Q5",  # annotations (could be controversial)
        "Q6",  # docs
        "Q7",  # changelog
        "S1",  # dunder all
        # "S3",
        # "D1", deprecation policy matters for maturity. You old enough to deprecate things.
        "C1",
        "C3",  # how did you publish
        "C4",  # lcok file
        "M1",  # pushed code recently... by definition, we're publishing today!!
    }
    eps_total = len(eps_set)
    eps_score = sum(
        1
        for check_id, result in results.items()
        if check_id in eps_set and result.passed
    )
    metrics.eps_score = eps_score
    metrics.eps_total = eps_total

    # things that mean you're done.
    # you don't need to start deprecating things to be done.
    completeness = {
        "C1",
        "C3",
        "C4",
        "Cmpl1",
        "Cmpl2",
        "Cmpl3",
        "Cmpl4",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "Q6",
        "Q7",
        # "Q8",
        # "R1", Can be done without distribution
        "R5",
        "R6",
        "S1",
    }
    completeness_total = len(completeness)
    completeness_score = sum(
        1
        for check_id, result in results.items()
        if check_id in completeness and result.passed
    )

    is_beta_candidate = (
        is_bad_score == is_bad_total
        and eps_score >= 12
        # and latest_version.major == 0 # version numbers are lies.
        # and results.get(
        #     "S3", CheckResult(passed=True, evidence="")
        # ).passed  # Assuming S3 passes for now
        # and results.get("R4 (12mo)", CheckResult(passed=False, evidence="")).passed  # passage of time seems arbitrary
        and completeness_score < 16
    )

    if is_beta_candidate and completeness_score < completeness_total:
        reason = f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total};"
        return "Development Status :: 4 - Beta", reason

    if eps_score >= 7 and completeness_score < 14 and is_bad_score > (is_bad_total - 2):
        return (
            "Development Status :: 3 - Alpha",
            f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total};",
        )

    if eps_score >= 4 and completeness_score < 10 and is_bad_score > (is_bad_total - 4):
        return (
            "Development Status :: 2 - Pre-Alpha",
            f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total};",
        )

    if eps_score >= 0 and completeness_score < 5:
        return (
            "Development Status :: 1 - Planning",
            f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total};",
        )

    is_production_candidate = (
        eps_score >= 12
        # and latest_version.major == 0 # version numbers are lies.
        # and results.get(
        #     "S3", CheckResult(passed=True, evidence="")
        # ).passed  # Assuming S3 passes for now
        # and results.get("R4 (12mo)", CheckResult(passed=False, evidence="")).passed  # passage of time seems arbitrary
        and completeness_score >= 16
    )

    long_term_support = {
        "Q7",  # Change log
        "D1",  # Deprecation policy
        "Q2",  # Multi python
        "R6",  # current python
        # TODO: should support current and last 5 pythons
        "M1",  # Easy to award but really, waiting doesn't mean anything about projects other than time passed.
    }

    # Long term support evidence
    long_term_support_total = len(long_term_support)
    long_term_support_score = sum(
        1
        for check_id, result in results.items()
        if check_id in long_term_support and result.passed
    )
    is_mature_candidate = long_term_support_score == long_term_support_total
    if is_production_candidate and is_mature_candidate and is_bad_score == is_bad_total:
        return (
            "Development Status :: 6 - Mature",
            f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total}; Long Term Support={long_term_support_score}/{long_term_support_total}",
        )
    if is_production_candidate:
        return (
            "Development Status :: 5 - Production/Stable",
            f"EPS={eps_score}/{eps_total}; Completeness={completeness_score}/{completeness_total};",
        )

    if is_bad_score < 3:
        return (
            "Development Status :: 1 - Planning",
            "Not enough complete to rate above Planning.",
        )

    return "Unknown", "Could not map to a development status based on checks."
