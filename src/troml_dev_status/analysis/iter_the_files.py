# --- utility: load .gitignore -----------------------------------------------
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Iterator, Set

import pathspec

_CODE_EXTS: tuple[str, ...] = (".py",)

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".eggs",
    ".idea",
    ".vscode",
    "site-packages",
}


def load_gitignore(repo_path: Path) -> pathspec.PathSpec | None:
    gitignore = repo_path / ".gitignore"
    if not gitignore.is_file():
        return None
    spec = pathspec.PathSpec.from_lines(
        "gitwildmatch", gitignore.read_text().splitlines()
    )
    return spec


# --- utility: walk with exclusions ------------------------------------------


def iter_repo_files(repo_path: Path, follow_symlinks: bool = False) -> Iterator[Path]:
    """
    Yield all files in repo_path, excluding:
      - .git, .venv, venv, node_modules, __pycache__, etc.
      - Anything ignored by .gitignore (if present).
    """
    skip_dirs: Set[str] = {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
    }

    gitignore_spec = load_gitignore(repo_path)

    for path in repo_path.rglob("*"):
        # Cheap directory pruning
        parts = set(path.parts)
        if parts & skip_dirs:
            continue

        # Only consider files
        try:
            if not (path.is_file() or (follow_symlinks and path.is_symlink())):
                continue
        except OSError:
            continue

        # Respect .gitignore
        if gitignore_spec:
            rel = str(path.relative_to(repo_path))
            if gitignore_spec.match_file(rel):
                continue

        yield path


def _iter_files(root: Path, exts: tuple[str, ...] = _CODE_EXTS) -> Iterable[Path]:
    yield from iter_files2(repo_path=root, include_exts=set(exts))
    # for p in root.rglob("*"):
    #     if p.is_file() and p.suffix in exts:
    #         # Skip typical vendor & virtual env dirs early
    #         if any(
    #             part in {".venv", "venv", "env", "site-packages", ".tox", ".git"}
    #             for part in p.parts
    #         ):
    #             continue
    #         yield p


_VENV_NAME_RE = re.compile(r"^(?:\.?venv|\.?env)(?:[-._]?\w+)*$", re.IGNORECASE)


def os_walk_no_follow(start: Path) -> Iterator[tuple[str, list[str], list[str]]]:
    for root, dirs, files in os.walk(start, topdown=True, followlinks=False):
        yield root, dirs, files


def _git_toplevel(start: Path) -> Path:
    """Best-effort: return the git repo root; fall back to `start` if not found."""
    cur = start.resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".git").exists():
            return p
    return start


def _load_gitignore_spec(repo_path: Path):
    """Load only the top-level .gitignore (avoid nested rebase pitfalls)."""
    try:
        repo_root = _git_toplevel(repo_path)
        gi = repo_root / ".gitignore"
        if not gi.exists():
            return None, repo_root
        lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
        spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        return spec, repo_root
    except Exception:
        return None, repo_path


def _is_ignored(repo_root: Path, p: Path, spec) -> bool:
    if spec is None:
        return False
    try:
        rel = p.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = p.as_posix()
    return spec.match_file(rel)


# from completness checks
def iter_files2(
    repo_path: Path,
    include_exts: set[str],
    respect_gitignore: bool = True,
) -> Iterator[Path]:
    """
    Yield files in repo_path with ext in include_exts (or "" for no ext),
    skipping common junk + venv-like dirs, and (optionally) honoring top-level .gitignore.
    """
    spec, repo_root = (
        _load_gitignore_spec(repo_path) if respect_gitignore else (None, repo_path)
    )

    for root, dirs, files in os_walk_no_follow(repo_path):
        root_path = Path(root)

        # Hard prune by name and venv-like patterns (works even w/o .gitignore)
        dirs[:] = [
            d for d in dirs if d not in _SKIP_DIRS and not _VENV_NAME_RE.match(d)
        ]

        for name in files:
            p = root_path / name

            if respect_gitignore and _is_ignored(repo_root, p, spec):
                continue

            ext = p.suffix
            if ext in include_exts or ("" in include_exts and ext == ""):
                yield p
