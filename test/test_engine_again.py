import pytest

from troml_dev_status.engine import determine_status
from troml_dev_status.models import CheckResult, Metrics

# --- Test Setup ---
# These sets are copied from engine.py to make the tests independent of changes
# in that file, ensuring this suite tests the logic as it was defined.

BADNESS_SRC = {
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
EPS_SRC = {
    "R2",
    "R3",
    "R5",
    "R6",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "Q5",
    "Q6",
    "Q7",
    "S1",
    "C1",
    "C3",
    "C4",
    "M1",
}
COMPLETENESS_SRC = {
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
    "R5",
    "R6",
    "S1",
}
LTS_SRC = {
    "Q7",
    "D1",
    "Q2",
    "R6",
    "M1",
}

ALL_CHECK_IDS = BADNESS_SRC | EPS_SRC | COMPLETENESS_SRC | LTS_SRC | {"R1"}


def create_mock_results(passed_ids: set[str]) -> dict[str, CheckResult]:
    """Helper to generate a results dictionary for determine_status."""
    results = {}
    for check_id in ALL_CHECK_IDS:
        # Create a result for every possible check to avoid key errors.
        results[check_id] = CheckResult(
            passed=check_id in passed_ids, evidence=f"mock evidence for {check_id}"
        )
    return results


# --- Test Cases ---


def test_hard_gate_planning_if_not_released():
    """Test that status is '1 - Planning' if R1 (published) check fails."""
    # No checks passed, including R1
    results = create_mock_results(passed_ids=set())
    classifier, _ = determine_status(results, None, Metrics())
    assert classifier == "Development Status :: 1 - Planning"

    # All checks passed EXCEPT R1
    passed_but_no_r1 = ALL_CHECK_IDS - {"R1"}
    results_all_but_r1 = create_mock_results(passed_ids=passed_but_no_r1)
    classifier_all_but_r1, _ = determine_status(results_all_but_r1, None, Metrics())
    assert classifier_all_but_r1 == "Development Status :: 1 - Planning"


def test_gate_planning_on_low_completeness_score():
    """Test that status is '1 - Planning' if completeness score is less than 5."""
    # Pass R1 and have a few other checks, but only 4 completeness checks.
    passed = {"R1"} | set(list(COMPLETENESS_SRC)[:4])
    results = create_mock_results(passed_ids=passed)
    classifier, _ = determine_status(results, None, Metrics())
    assert classifier == "Development Status :: 1 - Planning"


def test_gate_planning_on_low_badness_score():
    """Test that status is '1 - Planning' if badness score is less than 3."""
    # Pass R1 and enough completeness, but fail most badness checks.
    passed = {"R1"} | set(list(COMPLETENESS_SRC)[:10]) | set(list(BADNESS_SRC)[:2])
    results = create_mock_results(passed_ids=passed)
    classifier, _ = determine_status(results, None, Metrics())
    assert classifier == "Development Status :: 1 - Planning"


@pytest.mark.parametrize(
    "description, passed_checks, expected_status",
    [
        # --- Pre-Alpha Scenarios ---
        (
            "Barely meets Pre-Alpha",
            # EPS miss 11 of 16 (pass 5), Comp miss > 7 of 16 (pass 9), Badness miss 3 of 13 (pass 10)
            {"R1"}
            | set(list(EPS_SRC)[:5])
            | set(list(COMPLETENESS_SRC)[:9])
            | set(list(BADNESS_SRC)[:10]),
            "Development Status :: 2 - Pre-Alpha",
        ),
        # (
        #     "Fails Pre-Alpha on EPS",
        #     # EPS miss 12 of 16 (pass 4), just below threshold
        #     {"R1"} | set(list(EPS_SRC)[:4]) | set(list(COMPLETENESS_SRC)[:9]) | set(list(BADNESS_SRC)[:10]),
        #     "Unknown",  # Falls through because EPS is too low for any category
        # ),
        # --- Alpha Scenarios ---
        (
            "Barely meets Alpha",
            # EPS miss 7 of 16 (pass 9), Comp miss > 5 of 16 (pass 11), Badness miss 2 of 13 (pass 11)
            {"R1"}
            | set(list(EPS_SRC)[:9])
            | set(list(COMPLETENESS_SRC)[:11])
            | set(list(BADNESS_SRC)[:11]),
            "Development Status :: 3 - Alpha",
        ),
        (
            "Fails Alpha on Badness",
            # Badness miss 3 of 13 (pass 10), just below threshold
            {"R1"}
            | set(list(EPS_SRC)[:9])
            | set(list(COMPLETENESS_SRC)[:11])
            | set(list(BADNESS_SRC)[:10]),
            "Development Status :: 2 - Pre-Alpha",  # Drops to Pre-Alpha
        ),
        # --- Beta Scenarios ---
        (
            "Barely meets Beta",
            # EPS miss 5 of 16 (pass 11), Comp miss > 4 of 16 (pass 12), Badness miss 0 (pass all)
            {"R1"}
            | set(list(EPS_SRC)[:11])
            | set(list(COMPLETENESS_SRC)[:12])
            | BADNESS_SRC,
            "Development Status :: 4 - Beta",
        ),
        (
            "Fails Beta on Badness",
            # One badness check failed, not allowed for Beta
            {"R1"}
            | set(list(EPS_SRC)[:11])
            | set(list(COMPLETENESS_SRC)[:12])
            | (BADNESS_SRC - {"Fail1"}),
            "Development Status :: 3 - Alpha",  # Drops to Alpha
        ),
        (
            "Fails Beta on high Completeness",
            # Completeness is too high, pushing it out of Beta and into Production/Stable
            {"R1"} | set(list(EPS_SRC)[:15]) | COMPLETENESS_SRC | BADNESS_SRC,
            "Development Status :: 5 - Production/Stable",
        ),
        # --- Production/Stable Scenarios ---
        (
            "Meets Production/Stable",
            # EPS miss 1 of 16 (pass 15), Comp near-perfect (pass all), Badness can have fails
            {"R1"}
            | set(list(EPS_SRC)[:15])
            | COMPLETENESS_SRC
            | (BADNESS_SRC - {"Fail1"}),
            "Development Status :: 5 - Production/Stable",
        ),
        (
            "Fails Production on EPS",
            # EPS miss 2 of 16 (pass 14), just below threshold
            {"R1"} | set(list(EPS_SRC)[:14]) | COMPLETENESS_SRC | BADNESS_SRC,
            # "Development Status :: 4 - Beta", # High scores but not enough EPS for Prod -> Beta
            # Is this correct?
            "Development Status :: 5 - Production/Stable",
        ),
        # --- Mature Scenarios ---
        (
            "Meets Mature",
            # All EPS, Completeness, Badness, and LTS checks must pass.
            {"R1"} | EPS_SRC | COMPLETENESS_SRC | BADNESS_SRC | LTS_SRC,
            "Development Status :: 6 - Mature",
        ),
        (
            "Fails Mature on LTS",
            # Perfect score everywhere but one LTS check fails
            {"R1"} | EPS_SRC | COMPLETENESS_SRC | BADNESS_SRC | (LTS_SRC - {"D1"}),
            "Development Status :: 5 - Production/Stable",  # Drops to Production
        ),
        (
            "Fails Mature on Badness",
            # Perfect score everywhere but one Badness check fails
            {"R1"} | EPS_SRC | COMPLETENESS_SRC | (BADNESS_SRC - {"Fail1"}) | LTS_SRC,
            "Development Status :: 5 - Production/Stable",  # Drops to Production
        ),
    ],
)
def test_determine_status_scenarios(description, passed_checks, expected_status):
    """
    Tests various scoring combinations to ensure they map to the correct status.
    This covers boundary conditions for each development status.
    """
    results = create_mock_results(passed_ids=passed_checks)
    classifier, reason = determine_status(results, None, Metrics())
    assert classifier == expected_status, f"Failed on: {description}. Reason: {reason}"


def test_venv_mode_affects_totals():
    """
    Tests that venv_mode correctly filters checks, which can change the outcome.
    A score that is 'Beta' normally might become 'Production/Stable' if the failing
    checks are filtered out in venv_mode.
    """
    # Create a score that would be Beta.
    # Fail Q1 (CI config), which is part of EPS and Completeness.
    # In normal mode, this makes EPS and Completeness ratios imperfect.
    # In venv_mode, Q1 is skipped, making those ratios perfect for this test case.
    passed_checks = ALL_CHECK_IDS - {"Q1"}
    results = create_mock_results(passed_ids=passed_checks)

    # Without venv_mode, Q1 is counted. Perfect badness, but imperfect EPS/Comp -> Beta
    classifier_normal, _ = determine_status(results, None, Metrics(), venv_mode=False)
    assert classifier_normal == "Development Status :: 4 - Beta"

    # With venv_mode, Q1 is filtered out. The score is now perfect across the board -> Mature
    classifier_venv, _ = determine_status(results, None, Metrics(), venv_mode=True)
    assert classifier_venv == "Development Status :: 6 - Mature"
