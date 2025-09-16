import random
import string

import pytest
from packaging.version import Version

# Import the module under test
# Adjust the import if your test layout differs
from troml_dev_status.analysis import pypi as pypi_mod


def _random_nonexistent_name() -> str:
    # 24 random lowercase chars -> astronomically unlikely to exist
    return "zzz" + "".join(random.choices(string.ascii_lowercase, k=24))


@pytest.fixture(scope="module")
def requests_meta():
    """Real PyPI JSON for 'requests' (used for general behaviors)."""
    data = pypi_mod.get_project_data("requests")
    if data is None:
        pytest.skip("Network/PyPI unavailable (requests meta is None)")
    return data


@pytest.fixture(scope="module")
def sigstore_meta():
    """Real PyPI JSON for 'sigstore' (used to check attestations exist)."""
    data = pypi_mod.get_project_data("sigstore")
    if data is None:
        pytest.skip("Network/PyPI unavailable (sigstore meta is None)")
    return data


def test_get_project_data_existing_project():
    data = pypi_mod.get_project_data("requests")
    if data is None:
        pytest.skip("Network/PyPI unavailable (requests meta is None)")
    assert isinstance(data, dict)
    assert "info" in data
    assert data["info"]["name"].lower() == "requests"


def test_get_project_data_nonexistent_project_returns_none():
    name = _random_nonexistent_name()
    assert pypi_mod.get_project_data(name) is None


def test_get_sorted_versions_returns_desc_versions(requests_meta):
    versions = pypi_mod.get_sorted_versions(requests_meta)
    assert versions, "Expected at least one valid Version"
    assert all(isinstance(v, Version) for v in versions)
    # Check strictly non-increasing order
    assert versions == sorted(versions, reverse=True)


def test_latest_release_files_returns_version_and_files(requests_meta):
    version, files = pypi_mod.latest_release_files(requests_meta)
    # version comes from info.version (a str)
    assert isinstance(version, str) and version
    assert isinstance(files, list)
    # Each file dict should have a filename at minimum
    for f in files:
        assert "filename" in f


def test_file_has_attestations_handles_404_cleanly(requests_meta):
    project = requests_meta["info"]["name"]
    version, _files = pypi_mod.latest_release_files(requests_meta)
    # Ask for a nonsense filename to force 404
    has, data = pypi_mod.file_has_attestations(
        project, version, "this-file-does-not-exist.whl"
    )
    assert has is False
    assert data is None


@pytest.mark.timeout(60)
def test_latest_release_has_attestations_structure_for_requests():
    """We don't assert True/False (since not all projects have attestations),
    but we validate structure and types."""
    result = pypi_mod.latest_release_has_attestations("requests")
    if result is None:
        pytest.skip("Network/PyPI unavailable (requests)")
    assert isinstance(result, dict)
    for key in (
        "project",
        "version",
        "files",
        "any_file_attested",
        "all_files_attested",
    ):
        assert key in result
    assert isinstance(result["files"], list)
    for f in result["files"]:
        assert "filename" in f and "has_attestations" in f


@pytest.mark.timeout(120)
def test_sigstore_latest_has_attestations_true(sigstore_meta):
    """
    'sigstore' publicly documents releasing with SLSA/attestations.
    We assert at least one file in the latest release is attested.
    """
    project = sigstore_meta["info"]["name"]
    result = pypi_mod.latest_release_has_attestations(project)
    if result is None:
        pytest.skip("Network/PyPI unavailable (sigstore)")
    assert result["project"].lower() == "sigstore"
    assert result["files"], "Expected at least one file in latest release"
    assert (
        result["any_file_attested"] is True
    ), f"Expected at least one file to be attested for {project} {result['version']}"
