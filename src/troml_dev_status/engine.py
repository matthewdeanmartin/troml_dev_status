# troml_dev_status/engine.py
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Tuple

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
    check_ds10_core_metadata_present,
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
    results["Fail10"] = check_ds10_core_metadata_present(repo_path)
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


# Assuming these exist in your codebase:
# - CheckResult(passed: bool, evidence: str)
# - Metrics with attributes: eps_score, eps_total, eps_ratio (added), etc.


@dataclass(frozen=True)
class ScoreCard:
    score: int
    total: int
    ratio: float
    passed_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]  # present but not passed
    missing_ids: tuple[str, ...]  # not present in results

    @property
    def not_passed_ids(self) -> tuple[str, ...]:
        return tuple(self.failed_ids + self.missing_ids)


def _filter_checks_for_mode(
    check_ids: Iterable[str], venv_mode: bool, skip: set[str]
) -> set[str]:
    ids = set(check_ids)
    return ids - skip if venv_mode else ids


def _family_breakdown(
    results: Mapping[str, "CheckResult"], active_ids: Iterable[str]
) -> ScoreCard:
    active = list(active_ids)
    total = len(active)
    passed, failed, missing = [], [], []
    for cid in active:
        r = results.get(cid)
        if r is None:
            missing.append(cid)
        elif bool(getattr(r, "passed", False)):
            passed.append(cid)
        else:
            failed.append(cid)

    score = len(passed)
    ratio = 0.0 if total == 0 else score / total

    # Invariants / guards
    assert 0 <= score <= total, f"score out of bounds: {score}/{total}"  # nosec
    assert (
        -1e-9 <= ratio <= 1.0 + 1e-9
    ), f"ratio out of bounds: {ratio} for total={total}"  # nosec
    ratio = max(0.0, min(1.0, ratio))

    return ScoreCard(
        score=score,
        total=total,
        ratio=ratio,
        passed_ids=tuple(sorted(passed)),
        failed_ids=tuple(sorted(failed)),
        missing_ids=tuple(sorted(missing)),
    )


def _misses_to_ratio_allowable(misses_allowed: int, source_total: int) -> float:
    """
    Convert 'may miss N' (based on SOURCE total, i.e., pre-venv filtering) to a ratio threshold.
    Example: if source_total=20 and misses_allowed=5 -> threshold = 1 - 5/20 = 0.75
    """
    # If there are no source checks, demand a perfect ratio (conservative) to avoid divide-by-zero.
    if source_total <= 0:
        return 1.0
    threshold = 1.0 - (misses_allowed / source_total)
    assert (
        -1e-9 <= threshold <= 1.0 + 1e-9
    ), f"threshold out of bounds: {threshold}"  # nosec
    return max(0.0, min(1.0, threshold))


def _log_family(name: str, sc: ScoreCard) -> None:
    logger.debug(
        "%s: %s/%s (%.1f%%)  passed=%s  failed=%s  missing=%s",
        name,
        sc.score,
        sc.total,
        sc.ratio * 100,
        list(sc.passed_ids),
        list(sc.failed_ids),
        list(sc.missing_ids),
    )


def _log_rule(rule_name: str, condition: bool, note: str = "") -> None:
    logger.debug(
        "Rule %-14s -> %-5s  %s", rule_name, "PASS" if condition else "FAIL", note
    )


def determine_status(
    results: Mapping[str, "CheckResult"],
    latest_version,  # kept for possible future use
    metrics: "Metrics",
    venv_mode: bool = False,
    *,
    explain: bool = False,  # NEW (optional) – include detailed breakdown in the reason string
) -> Tuple[str, str]:
    """
    Determine development status using ratio-based thresholds.
    Readability rule of thumb:
      - Keep human intent as "alpha can miss N of X", "beta can miss M of Y", etc.
      - Convert those 'miss N' statements into ratio thresholds using SOURCE totals
        (before venv filtering), then compare using the observed ratios (after filtering).
    """
    if os.environ.get("TROML_DEV_STATUS_VENV_MODE"):
        venv_mode = True
    # --- Hard gate: "Unclassifiable" if never released ---
    if not results.get("R1", type("X", (), {"passed": False})()).passed:
        logger.debug("Hard gate: R1 failed or missing -> Planning")
        return "Development Status :: 1 - Planning", "Project has no releases on PyPI."

    # --- Define check families (source sets) ---
    # --- Define source sets (pre-venv) ---
    badness_src = {
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

    # Early Phase Score (“EPS”) signals early readiness.
    eps_src = {
        "R2",  # wheel/sdist
        "R3",  # PEP 440
        "R5",  # declares Python
        "R6",  # supports current Python
        "Q1",
        "Q2",  # CI config & multi-python
        "Q3",
        "Q4",  # tests present & test ratio
        "Q5",  # annotations
        "Q6",  # docs present
        "Q7",  # changelog
        "S1",  # __all__ exports
        "C1",
        "C3",
        "C4",  # compliance / publishing / lock file
        "M1",  # recent code push
    }

    # Completeness signals “done-ness”
    completeness_src = {
        "C1",  # security.md
        "C3",  # pinned dependencies
        "C4",  # lock files
        "Cmpl1",  # TODO
        "Cmpl2",  # not impl
        "Cmpl3",  # pass
        "Cmpl4",  # stub files
        "Q1",  # ci
        "Q2",  # multipython
        "Q3",  # test count
        "Q4",  # annotations
        "Q6",  # docs
        "Q7",  # change log
        # "Q8", intentionally excluded per your comment
        # "R1", can be done without distribution
        "R5",
        "R6",
        "S1",
    }

    # Long-term support signals for “Mature”
    lts_src = {
        "Q7",  # Changelog
        "D1",  # Deprecation policy
        "Q2",  # Multi Python
        "R6",  # Current Python
        "M1",  # Time passing alone isn’t quality, but included per original logic
    }

    # Checks that we skip when in venv mode
    skip_in_venv = {
        "Q1",
        "Q2",  # CI config
        "Q3",
        "Q4",  # test files / ratio
        "C4",  # lockfiles
        "C1",
        "Q6",
        "Q8",
        "Q9",  # “bureaucracy” files
    }

    # Active sets (post-venv)
    badness_ids = _filter_checks_for_mode(badness_src, venv_mode, skip_in_venv)
    eps_ids = _filter_checks_for_mode(eps_src, venv_mode, skip_in_venv)
    comp_ids = _filter_checks_for_mode(completeness_src, venv_mode, skip_in_venv)
    lts_ids = _filter_checks_for_mode(lts_src, venv_mode, skip_in_venv)

    # Scorecards
    badness = _family_breakdown(results, badness_ids)
    eps = _family_breakdown(results, eps_ids)
    comp = _family_breakdown(results, comp_ids)
    lts = _family_breakdown(results, lts_ids)

    # Log families up-front
    _log_family("BADNESS", badness)
    _log_family("EPS", eps)
    _log_family("COMPLETENESS", comp)
    _log_family("LTS", lts)

    # Export some metrics
    metrics.eps_score = eps.score
    metrics.eps_total = eps.total
    # Optionally store the ratios too (helps testing & reporting)
    if hasattr(metrics, "eps_ratio"):
        metrics.eps_ratio = eps.ratio

    # Thresholds (based on SOURCE totals, to keep “miss N” readable)
    eps_beta_thr = _misses_to_ratio_allowable(5, len(eps_src))
    comp_beta_max = _misses_to_ratio_allowable(4, len(completeness_src)) - 1e-12
    eps_alpha_thr = _misses_to_ratio_allowable(7, len(eps_src))
    comp_alpha_max = _misses_to_ratio_allowable(5, len(completeness_src)) - 1e-12
    bad_alpha_thr = _misses_to_ratio_allowable(2, len(badness_src))
    eps_prealpha_thr = _misses_to_ratio_allowable(11, len(eps_src))
    comp_prealpha_max = _misses_to_ratio_allowable(7, len(completeness_src)) - 1e-12
    bad_prealpha_thr = _misses_to_ratio_allowable(3, len(badness_src))
    eps_prod_thr = _misses_to_ratio_allowable(1, len(eps_src))
    comp_prod_min = 0.99

    # Helper to assemble optional verbose reason text
    def detailed_reason(header: str) -> str:
        if not explain:
            return header
        lines = [
            header,
            f"EPS: {eps.score}/{eps.total} ({eps.ratio:.2%})",
            f"  not-passed={list(eps.not_passed_ids)}",
            f"COMPLETENESS: {comp.score}/{comp.total} ({comp.ratio:.2%})",
            f"  not-passed={list(comp.not_passed_ids)}",
            f"BADNESS: {badness.score}/{badness.total} ({badness.ratio:.2%})",
            f"  not-passed={list(badness.not_passed_ids)}",
            f"LTS: {lts.score}/{lts.total} ({lts.ratio:.2%})",
            f"  not-passed={list(lts.not_passed_ids)}",
        ]
        return "\n".join(lines)

    # --- Rules with logging ---
    # Beta
    cond_beta = (
        badness.ratio >= _misses_to_ratio_allowable(0, len(badness_src))
        and eps.ratio >= eps_beta_thr
        and comp.ratio < comp_beta_max
    )
    _log_rule(
        "Beta",
        cond_beta,
        note=f"badness>={badness.ratio:.2f}, eps>={eps.ratio:.2f} (thr={eps_beta_thr:.2f}), comp<{comp_beta_max:.2f}",
    )
    if cond_beta:
        return "Development Status :: 4 - Beta", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # Alpha
    cond_alpha = (
        eps.ratio >= eps_alpha_thr
        and comp.ratio < comp_alpha_max
        and badness.ratio >= bad_alpha_thr
    )
    _log_rule(
        "Alpha",
        cond_alpha,
        note=f"eps>={eps_alpha_thr:.2f}, comp<{comp_alpha_max:.2f}, badness>={bad_alpha_thr:.2f}",
    )
    if cond_alpha:
        return "Development Status :: 3 - Alpha", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # Pre-Alpha
    cond_prealpha = (
        eps.ratio >= eps_prealpha_thr
        and comp.ratio < comp_prealpha_max
        and badness.ratio >= bad_prealpha_thr
    )
    _log_rule(
        "Pre-Alpha",
        cond_prealpha,
        note=f"eps>={eps_prealpha_thr:.2f}, comp<{comp_prealpha_max:.2f}, badness>={bad_prealpha_thr:.2f}",
    )
    if cond_prealpha:
        return "Development Status :: 2 - Pre-Alpha", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # Planning (early bail)
    cond_planning_low_comp = comp.score < 5
    _log_rule(
        "PlanningLowComp", cond_planning_low_comp, note=f"comp.score={comp.score} < 5"
    )
    if cond_planning_low_comp:
        return "Development Status :: 1 - Planning", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # Production / Mature
    is_production = eps.ratio >= eps_prod_thr and comp.ratio >= comp_prod_min
    _log_rule(
        "Production",
        is_production,
        note=f"eps>={eps_prod_thr:.2f}, comp>={comp_prod_min:.2f}",
    )
    if is_production:
        lts_all_met = lts.total > 0 and lts.score == lts.total
        badness_clean = badness.score == badness.total
        _log_rule("MatureLTS", lts_all_met, note=f"LTS={lts.score}/{lts.total}")
        _log_rule("MatureBadnessClean", badness_clean)
        if lts_all_met and badness_clean:
            return "Development Status :: 6 - Mature", detailed_reason(
                f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}; LTS={lts.score}/{lts.total}"
            )
        return "Development Status :: 5 - Production/Stable", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # Safety net
    cond_planning_bad = badness.score < 3
    _log_rule(
        "PlanningBadnessLow",
        cond_planning_bad,
        note=f"badness.score={badness.score} < 3",
    )
    if cond_planning_bad:
        return (
            "Development Status :: 1 - Planning",
            "Not enough complete to rate above Planning.",
        )

        # --- New Top-Down Classification Logic ---

        # 1. Check for Mature (most strict)
    is_production = eps.ratio >= eps_prod_thr and comp.ratio >= comp_prod_min
    if is_production:
        is_mature = (lts.total > 0 and lts.score == lts.total) and (
            badness.score == badness.total
        )
        if is_mature:
            return "Development Status :: 6 - Mature", detailed_reason(
                f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}; LTS={lts.score}/{lts.total}"
            )

        # 2. Check for Production/Stable (if not Mature)
        return "Development Status :: 5 - Production/Stable", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # 3. Check for Beta
    # This condition no longer needs to check an upper bound for completeness.
    is_beta = badness.ratio >= 1.0 and eps.ratio >= eps_beta_thr
    if is_beta:
        return "Development Status :: 4 - Beta", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # 4. Check for Alpha
    is_alpha = eps.ratio >= eps_alpha_thr and badness.ratio >= bad_alpha_thr
    if is_alpha:
        return "Development Status :: 3 - Alpha", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # 5. Check for Pre-Alpha
    is_pre_alpha = eps.ratio >= eps_prealpha_thr and badness.ratio >= bad_prealpha_thr
    if is_pre_alpha:
        return "Development Status :: 2 - Pre-Alpha", detailed_reason(
            f"EPS={eps.score}/{eps.total}; Completeness={comp.score}/{comp.total}"
        )

    # 6. Else, it must be Planning
    # All other cases fall through to the lowest valid status.
    return "Development Status :: 1 - Planning", detailed_reason(
        "Project scores do not meet the criteria for Pre-Alpha or higher."
    )
    logger.debug("Fall-through -> Unknown")
    return "Unknown", "Could not map to a development status based on checks."
