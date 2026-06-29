from pathlib import Path

from troml_dev_status.analysis.find_tests import _count_unittest


def test_unittest_discovery_survives_non_importable_dir(tmp_path: Path):
    """A tests/ dir without __init__.py is not importable by unittest discovery.

    This is extremely common (pytest projects rarely add __init__.py to tests/).
    Previously unittest's loader.discover() raised ImportError and crashed the
    whole analysis; now the un-importable dir is skipped gracefully.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_thing.py").write_text(
        "def test_thing():\n    assert True\n", encoding="utf-8"
    )

    # Should not raise; returns a count (0 because the dir isn't importable
    # for unittest, which is fine — pytest collection handles these projects).
    count = _count_unittest(tmp_path, ("test", "tests"))
    assert isinstance(count, int)
