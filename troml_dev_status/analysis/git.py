# troml_dev_status/analysis/git.py
from __future__ import annotations

import logging
import subprocess  # nosec
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_git_command(cwd: Path, *args: str) -> str | None:
    """Helper to run a git command and return its output."""
    try:
        result = subprocess.run(  # nosec
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_latest_commit_date(repo_path: Path, sub_path: str = "src") -> datetime | None:
    """Finds the timestamp of the last commit to touch a specific subdirectory."""
    path_spec = (repo_path / sub_path).relative_to(repo_path)
    output = _run_git_command(
        repo_path, "log", "-1", "--format=%ct", "--", str(path_spec)
    )
    if output and output.isdigit():
        return datetime.fromtimestamp(int(output), tz=timezone.utc)
    return None


def is_tag_signed(repo_path: Path, tag_name: str) -> bool:
    """Checks if a given Git tag is GPG signed and valid."""
    # `git tag -v` returns 0 if signed and valid, non-zero otherwise.
    # We capture stderr to prevent it from printing to the console on failure.
    try:
        subprocess.run(  # nosec
            ["git", "-C", str(repo_path), "tag", "-v", tag_name],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_tags_by_date(repo_path: Path) -> list[str]:
    """Returns a list of all tags, sorted by date (newest first)."""
    output = _run_git_command(repo_path, "tag", "--sort=-creatordate")
    return output.splitlines() if output else []


def get_file_content_at_tag(repo_path: Path, tag: str, file_path: str) -> str | None:
    """Retrieves the content of a file at a specific Git tag."""
    return _run_git_command(repo_path, "show", f"{tag}:{file_path}")
