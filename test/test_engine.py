import pytest

from troml_dev_status.engine import determine_status
from troml_dev_status.models import CheckResult, Metrics


def ck(passed: bool, evidence: str = "") -> CheckResult:
    return CheckResult(passed=passed, evidence=evidence)


def base_results():
    """
    Start from a dict where every referenced check exists and defaults to False.
    This avoids KeyError/branching surprises when we selectively flip checks on.
    """
    checks = {
        # Release / packaging
        "R1": ck(False),
        "R2": ck(False),
        "R3": ck(False),
        "R4 (12mo)": ck(False),
        "R5": ck(False),
        "R6": ck(False),
        # Quality
        "Q1": ck(False),
        "Q2": ck(False),
        "Q3": ck(False),
        "Q4": ck(False),
        "Q5": ck(False),
        "Q6": ck(False),
        "Q7": ck(False),
        "Q8": ck(False),
        "Q9": ck(False),
        # Security/structure/etc.
        "S1": ck(False),
        "D1": ck(False),
        "C1": ck(False),
        "C2": ck(False),
        "C3": ck(False),
        "C4": ck(False),
        # Completeness family
        "Cmpl1": ck(False),
        "Cmpl2": ck(False),
        "Cmpl3": ck(False),
        "Cmpl4": ck(False),
        # Maintenance
        "M1": ck(False),
        "M2 (12mo)": ck(False),
    }
    return checks


def test_planning_when_no_release():
    results = base_results()
    # R1 failing short-circuits to Planning.
    results["R1"] = ck(False, "No releases")
    status, reason = determine_status(results, latest_version=None, metrics=Metrics())
    assert status == "Development Status :: 1 - Planning"
    assert "no releases" in reason.lower() or "has no releases" in reason.lower()


def test_planning_when_release_but_low_completeness():
    results = base_results()
    results["R1"] = ck(True)  # has a release
    # Keep EPS low and completeness < 5
    # (leave everything else False)
    for bad in {
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
    }:
        results[bad] = ck(True)
    status, _ = determine_status(results, latest_version=None, metrics=Metrics())
    assert status == "Development Status :: 1 - Planning"


def test_pre_alpha_path():
    results = base_results()
    results["R1"] = ck(True)
    # EPS needs >= 4. Use any 4 from eps_set.
    for k in ["Q1", "Q2", "Q3", "R3"]:
        results[k] = ck(True)
    # Completeness must be < 10
    # Turn on a couple but keep below 10
    for k in ["Q1", "Q2"]:
        results[k] = ck(True)
    for bad in {
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
    }:
        results[bad] = ck(True)
    status, _ = determine_status(results, None, Metrics())
    assert status == "Development Status :: 2 - Pre-Alpha"


def test_alpha_path():
    results = base_results()
    results["R1"] = ck(True)
    # EPS >= 7
    for k in ["Q1", "Q2", "Q3", "Q4", "R3", "R5", "R6"]:
        results[k] = ck(True)
    # Completeness < 14
    # Flip a handful (still below 14)
    for k in ["Q1", "Q2", "Q3", "Q4", "Q6", "Q7", "R5", "R6", "S1"]:
        results[k] = ck(True)
    for bad in {
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
    }:
        results[bad] = ck(True)
    status, _ = determine_status(results, None, Metrics())
    assert status == "Development Status :: 3 - Alpha"


def test_beta_path():
    results = base_results()
    results["R1"] = ck(True)
    # EPS >= 12 — enable 12 from eps_set
    for k in ["R2", "R3", "R5", "R6", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "S1"]:
        results[k] = ck(True)
    # Completeness < 16 — make sure at least one completeness check is False
    for k in ["C1", "C3", "C4", "Cmpl1", "Cmpl2", "Cmpl3", "Cmpl4"]:
        results[k] = ck(False)
    for bad in {
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
    }:
        results[bad] = ck(True)
    status, _ = determine_status(results, None, Metrics())
    assert status == "Development Status :: 4 - Beta"


def test_production_path():
    results = base_results()
    results["R1"] = ck(True)
    # EPS >= 12 (turn many on)
    for k in ["R2", "R3", "R5", "R6", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "S1"]:
        results[k] = ck(True)
    # Completeness == 16 (all completeness checks True)
    for k in ["C1", "C3", "C4", "Cmpl1", "Cmpl2", "Cmpl3", "Cmpl4"]:
        results[k] = ck(True)
    # But not all long term support (to avoid Mature)
    # LTS = {"Q7","D1","Q2","R6","M1"}
    results["D1"] = ck(False)
    results["M1"] = ck(True)  # a few true, but not all

    for bad in {
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
    }:
        results[bad] = ck(True)

    status, _ = determine_status(results, None, Metrics())
    assert status == "Development Status :: 5 - Production/Stable"


def test_mature_path():
    results = base_results()
    results["R1"] = ck(True)
    # EPS >= 12
    for k in ["R2", "R3", "R5", "R6", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "S1"]:
        results[k] = ck(True)
    # Completeness = 16
    for k in ["C1", "C3", "C4", "Cmpl1", "Cmpl2", "Cmpl3", "Cmpl4"]:
        results[k] = ck(True)
    # Long-term support all True: {"Q7", "D1", "Q2", "R6", "M1"}
    results["D1"] = ck(True)
    results["M1"] = ck(True)

    for bad in {
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
    }:
        results[bad] = ck(True)

    status, _ = determine_status(results, None, Metrics())
    assert status == "Development Status :: 6 - Mature"


@pytest.mark.parametrize(
    "flip_true,flip_false",
    [
        # A few “random but realistic” mixes that should still never yield Unknown.
        (["R1", "Q1", "Q2", "Q3", "R3"], []),  # pre-alpha-ish
        (
            ["R1", "Q1", "Q2", "Q3", "Q4", "R3", "R5", "R6"],
            ["Cmpl1", "Cmpl2"],
        ),  # alpha-ish
        (
            [
                "R1",
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
            ],
            ["C1", "C3", "C4"],
        ),  # beta-ish (EPS high, completeness not full)
    ],
)
def test_never_unknown_for_realistic_states(flip_true, flip_false):
    results = base_results()
    for k in flip_true:
        results[k] = ck(True)
    for k in flip_false:
        results[k] = ck(False)
    # Ensure release exists unless caller explicitly flipped it off
    if "R1" not in flip_true and "R1" not in flip_false:
        results["R1"] = ck(True)
    status, _ = determine_status(results, None, Metrics())
    assert status != "Unknown"
