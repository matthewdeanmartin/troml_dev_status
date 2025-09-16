# troml_dev_status/analysis/filesystem.py

from __future__ import annotations

import ast
from pathlib import Path

import tomlkit
import yaml

# Use tomllib for Python 3.11+, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]


DEV_STATUS_PREFIX = "Development Status :: "


def _load_pyproject_doc(repo_path: Path):
    """Return a tomlkit document (if tomlkit available) or a plain dict.
    Caller should branch on tomlkit availability when writing back.
    """
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        raise FileNotFoundError(pyproject)

    content = pyproject.read_text(encoding="utf-8")
    if tomlkit is not None:
        return tomlkit.parse(content)
    # Fallback to std loader (loses comments on write!)
    with pyproject.open("rb") as f:
        return tomllib.load(f)


def _dump_pyproject_doc(repo_path: Path, doc) -> None:
    pyproject = repo_path / "pyproject.toml"
    if tomlkit is not None and isinstance(doc, tomlkit.TOMLDocument):  # type: ignore[attr-defined]
        pyproject.write_text(tomlkit.dumps(doc), encoding="utf-8")
        return
    # Fallback: best-effort rewrite; comments will be lost.
    import io

    io.StringIO()
    # Very small dependency-less dumper using tomli-w could be used, but avoid new deps beyond tomlkit.
    # We'll use repr for safety if tomlkit missing; recommend installing tomlkit.
    raise RuntimeError(
        "tomlkit is required for safe in-place updates preserving comments. Please install tomlkit."
    )


def _ensure_project_table(doc):
    if "project" not in doc:
        if tomlkit is None:
            raise RuntimeError("tomlkit required to create missing [project] table.")
        doc["project"] = tomlkit.table()
    return doc["project"]


def _get_classifiers_list(project_table) -> list:
    cls = project_table.get("classifiers")
    if cls is None:
        return []
    # tomlkit arrays behave like lists
    return list(cls)  # make a copy for easy manipulation


def get_dev_status_classifier(repo_path: Path) -> str | None:
    """Return the first declared Development Status trove classifier, or None."""
    try:
        doc = _load_pyproject_doc(repo_path)
    except FileNotFoundError:
        return None

    project = doc.get("project", {})
    classifiers = project.get("classifiers")
    if not classifiers:
        return None

    for c in classifiers:
        if isinstance(c, str) and c.startswith(DEV_STATUS_PREFIX):
            return c
    return None


def set_dev_status_classifier(repo_path: Path, new_classifier: str) -> bool:
    """Set/replace the Development Status classifier in pyproject.toml.

    - Creates [project] and classifiers array if missing.
    - Removes any existing Development Status entries.
    - Inserts the new classifier (stable position: front of the list).
    - Preserves comments/formatting when tomlkit is available.
    """
    doc = _load_pyproject_doc(repo_path)

    project = _ensure_project_table(doc)

    if "classifiers" not in project or project.get("classifiers") is None:
        if tomlkit is None:
            raise RuntimeError(
                "tomlkit required to create missing project.classifiers."
            )
        project["classifiers"] = tomlkit.array().multiline(True)  # pretty

    # Normalize into a mutable list (tomlkit Array supports list ops)
    cls = project["classifiers"]

    # Remove any existing Dev Status entries
    to_keep = []
    for item in cls:
        if not (isinstance(item, str) and item.startswith(DEV_STATUS_PREFIX)):
            to_keep.append(item)
    # Reset array then append back items, then add the new one at front
    if hasattr(cls, "clear"):
        cls.clear()  # type: ignore[attr-defined]
    for item in to_keep:
        cls.append(item)
    # Put dev status at the beginning for visibility
    cls.insert(0, new_classifier)

    _dump_pyproject_doc(repo_path, doc)
    return True


def get_project_name(repo_path: Path) -> str | None:
    """Parses pyproject.toml to find the project name."""
    toml_path = repo_path / "pyproject.toml"
    if not toml_path.exists():
        return None
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("name")
    except tomllib.TOMLDecodeError:
        return None


def get_analysis_mode(repo_path: Path) -> str:
    """
    Parses pyproject.toml to find the analysis mode from [tool.troml-dev-status].
    Defaults to 'library' if not specified or invalid.
    """
    toml_path = repo_path / "pyproject.toml"
    if not toml_path.exists():
        return "library"  # Default if no pyproject.toml
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        # Look in [tool.troml-dev-status].mode
        tool_config = data.get("tool", {}).get("troml-dev-status", {})
        mode = tool_config.get("mode", "library")
        if mode not in ["library", "application"]:
            return "library"  # Fallback for invalid value
        return mode
    except tomllib.TOMLDecodeError:
        return "library"  # Default on parse error


def get_project_dependencies(repo_path: Path) -> list[str] | None:
    """Parses pyproject.toml to get the list of runtime dependencies."""
    toml_path = repo_path / "pyproject.toml"
    if not toml_path.exists():
        return None
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        # PEP 621 specifies dependencies are in [project].dependencies
        return data.get("project", {}).get("dependencies")
    except tomllib.TOMLDecodeError:
        return None


def find_src_dir(repo_path: Path) -> Path | None:
    """Finds the primary source directory (e.g., 'src/', or the package dir)."""
    if (repo_path / "src").is_dir():
        return repo_path / "src"

    name = get_project_name(repo_path)
    if name and (repo_path / name).is_dir():
        return repo_path / name
    if name and (repo_path / name.replace("-", "_")).is_dir():
        return repo_path / name.replace("-", "_")
    return None


def count_test_files(repo_path: Path) -> int:
    """Counts files matching test patterns."""
    total = 0
    for dir_name in ["test", "tests"]:
        tests_dir = repo_path / dir_name
        if not tests_dir.is_dir():
            continue
        found = len(list(tests_dir.glob("**/test_*.py"))) + len(
            list(tests_dir.glob("**/*_test.py"))
        )
        total += found
    return total


def count_source_modules(src_path: Path) -> int:
    """Counts non-__init__.py Python modules in the source directory."""
    if not src_path or not src_path.is_dir():
        return 0
    return sum(
        1 for f in src_path.rglob("*.py") if f.is_file() and f.name != "__init__.py"
    )


def get_ci_config_files(repo_path: Path) -> list[Path]:
    """Finds common CI configuration files."""
    patterns = [".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml"]
    files = []
    for pattern in patterns:
        files.extend(list(repo_path.glob(pattern)))
    return files


def has_multi_python_in_ci(ci_files: list[Path]) -> bool:
    """A simple check to see if CI files mention multiple Python versions."""
    py_versions = set()
    for file_path in ci_files:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
                # Simple string search, not a full parse. Good enough for an objective signal.
                if "3.9" in content:
                    py_versions.add("3.9")
                if "3.10" in content:
                    py_versions.add("3.10")
                if "3.11" in content:
                    py_versions.add("3.11")
                if "3.12" in content:
                    py_versions.add("3.12")
                if "3.13" in content:
                    py_versions.add("3.13")
        except (IOError, yaml.YAMLError):
            continue
    return len(py_versions) >= 2


def analyze_type_hint_coverage(src_path: Path) -> tuple[float, int]:
    """
    Calculates the percentage of public functions/methods with type hints.
    Returns (coverage_percentage, total_public_symbols).
    """
    if not src_path or not src_path.is_dir():
        return 0.0, 0

    total_symbols = 0
    annotated_symbols = 0

    for py_file in src_path.rglob("*.py"):
        try:
            with py_file.open("r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Is it public? (not starting with _)
                if not node.name.startswith("_"):
                    total_symbols += 1
                    # Is it annotated? (return annotation is sufficient)
                    if node.returns is not None:
                        annotated_symbols += 1

    if total_symbols == 0:
        return 0.0, 0

    coverage = (annotated_symbols / total_symbols) * 100
    return coverage, total_symbols


def get_bureaucracy_files(repo_path: Path):
    # could be in any case, could be with or without extension, could
    patterns = ["security.md", "contributing.md", "code_of_conduct.md"]
    files = []
    for pattern in patterns:
        files.extend(list(repo_path.glob(pattern)))
    return files
