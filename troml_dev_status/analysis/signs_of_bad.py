"""
Egregious "do-not-use" static checks for troml_dev_status.
- Focus: incompetence/sloth/incompleteness, *no* code execution/imports.
- Dead-code % checks intentionally deferred (hard problem; do later).

Each check returns CheckResult(passed: bool, evidence: str).

Integrate by importing these into checks.py or wiring into engine.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

# Use tomllib for Python 3.11+, fallback to tomli for older versions
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

import re
from datetime import datetime, timezone

from troml_dev_status.models import CheckResult

# ---- helpers ---------------------------------------------------------------

_CODE_EXTS: Tuple[str, ...] = (".py",)

_STD_LIB_MODULES: Set[str] = {
    # trimmed; good enough heuristic for the "pointless content" check
    "os",
    "sys",
    "pathlib",
    "typing",
    "dataclasses",
    "logging",
    "json",
    "re",
    "math",
    "itertools",
    "functools",
    "collections",
    "subprocess",
    "shutil",
    "argparse",
    "typing_extensions",
    "inspect",
    "time",
    "datetime",
    "base64",
}


def _iter_files(root: Path, exts: Tuple[str, ...] = _CODE_EXTS) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in exts:
            # Skip typical vendor & virtual env dirs early
            if any(
                part in {".venv", "venv", "env", "site-packages", ".tox", ".git"}
                for part in p.parts
            ):
                continue
            yield p


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return None
    except Exception:
        return None


def _nonempty_loc(text: str) -> int:
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        count += 1
    return count


def _module_ast(path: Path) -> Optional[ast.AST]:
    src = _read_text(path)
    if src is None:
        return None
    try:
        return ast.parse(src, filename=str(path))
    except SyntaxError:
        return None


def _has_only_empty_init(root: Path) -> bool:
    py_files = list(_iter_files(root))
    if not py_files:
        return False
    non_init = [p for p in py_files if p.name != "__init__.py"]
    if non_init:
        return False
    # Only __init__.py files present; check they are empty/trivial
    for p in py_files:
        txt = _read_text(p) or ""
        if _nonempty_loc(txt) > 0:
            return False
    return True


def _package_dirs_missing_init(root: Path) -> List[Path]:
    missing: List[Path] = []
    for d in {p.parent for p in _iter_files(root)}:
        if (d / "__init__.py").exists():
            continue
        # has at least one .py but no __init__.py → not a proper package
        if any(child.suffix == ".py" for child in d.iterdir() if child.is_file()):
            missing.append(d)
    return missing


def _is_stub_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = node.body
    if not body:
        return True
    # Single-statement bodies that are pass/raise NIE/return literal/None
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call):
            func = stmt.exc.func
            if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                return True
        if isinstance(stmt, ast.Return):
            if stmt.value is None:
                return True
            if isinstance(stmt.value, (ast.Constant,)) and stmt.value.value in (
                None,
                0,
                "",
            ):
                return True
    # Docstring-only bodies count as stub
    if (
        len(body) == 1
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return True
    return False


def _stub_density(root: Path) -> Tuple[int, int, float]:
    stub = 0
    total = 0
    for path in _iter_files(root):
        mod = _module_ast(path)
        if mod is None:
            continue
        for node in ast.walk(mod):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total += 1
                if _is_stub_func(node):
                    stub += 1
    density = (stub / total) if total else 0.0
    return stub, total, density


def _top_level_imports(root: Path) -> Set[str]:
    seen: Set[str] = set()
    for path in _iter_files(root):
        mod = _module_ast(path)
        if mod is None:
            continue
        for node in mod.body:  # type: ignore[attr-defined]
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen.add((alias.name.split(".")[0]))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    seen.add(node.module.split(".")[0])  # type: ignore[attr-defined]
    return seen


# ---- checks: massive incompleteness ----------------------------------------


def check_ds0_zero_file_count(repo_path: Path) -> CheckResult:
    """Fail if there are zero Python source files in the repo (excluding env/vendor dirs)."""
    files = list(_iter_files(repo_path))
    if not files:
        return CheckResult(
            passed=False, evidence="No Python source files found (0 files)."
        )
    return CheckResult(passed=True, evidence=f"Found {len(files)} Python files.")


def check_ds1_tiny_codebase(repo_path: Path, min_nonempty_loc: int = 10) -> CheckResult:
    """Fail if total non-empty, non-comment LOC across all .py files is below threshold."""
    total = 0
    for p in _iter_files(repo_path):
        txt = _read_text(p) or ""
        total += _nonempty_loc(txt)
    if total < min_nonempty_loc:
        return CheckResult(
            passed=False, evidence=f"Only {total} non-empty LOC (< {min_nonempty_loc})."
        )
    return CheckResult(passed=True, evidence=f"Total non-empty LOC: {total}.")


def check_ds2_all_empty_files(repo_path: Path) -> CheckResult:
    """Fail if *all* Python files are empty or comment-only (no non-empty LOC)."""
    files = list(_iter_files(repo_path))
    if not files:
        return CheckResult(passed=False, evidence="No Python files to analyze.")
    nonempty = 0
    for p in files:
        txt = _read_text(p) or ""
        if _nonempty_loc(txt) > 0:
            nonempty += 1
    if nonempty == 0:
        return CheckResult(
            passed=False,
            evidence=f"All {len(files)} Python files are empty/comment-only.",
        )
    return CheckResult(
        passed=True, evidence=f"{nonempty}/{len(files)} files contain non-empty code."
    )


def check_ds3_only_empty_init(repo_path: Path) -> CheckResult:
    """Fail if the codebase contains only __init__.py files and they are empty/trivial."""
    if _has_only_empty_init(repo_path):
        return CheckResult(
            passed=False, evidence="Repository contains only empty __init__.py files."
        )
    return CheckResult(passed=True, evidence="Has code beyond empty __init__.py.")


def check_ds4_missing_package_init(repo_path: Path) -> CheckResult:
    """Fail if directories containing .py files are missing __init__.py (import impossible)."""
    missing = _package_dirs_missing_init(repo_path)
    if missing:
        sample = ", ".join(str(p) for p in missing[:5])
        more = "" if len(missing) <= 5 else f" (+{len(missing)-5} more)"
        return CheckResult(
            passed=False, evidence=f"Package dirs without __init__.py: {sample}{more}."
        )
    return CheckResult(passed=True, evidence="All package dirs include __init__.py.")


# ---- checks: can’t parse (static only) -------------------------------------


def check_ds5_unparsable_python(repo_path: Path) -> CheckResult:
    """Fail if any .py fails AST parsing (syntax error or unreadable file)."""
    bad: List[str] = []
    for p in _iter_files(repo_path):
        mod = _module_ast(p)
        if mod is None:
            bad.append(str(p))
    if bad:
        sample = ", ".join(bad[:5])
        more = "" if len(bad) <= 5 else f" (+{len(bad)-5} more)"
        return CheckResult(
            passed=False, evidence=f"Unparsable Python files: {sample}{more}."
        )
    return CheckResult(passed=True, evidence="All Python files parsed successfully.")


def check_ds6_py_extension_nonpython(repo_path: Path) -> CheckResult:
    """Fail if .py file appears binary/non-text or contains null bytes; heuristic for mislabeled content."""
    bad: List[str] = []
    for p in _iter_files(repo_path):
        try:
            data = p.read_bytes()
        except Exception:
            bad.append(str(p))
            continue
        if b"\x00" in data:
            bad.append(str(p))
    if bad:
        sample = ", ".join(bad[:5])
        more = "" if len(bad) <= 5 else f" (+{len(bad)-5} more)"
        return CheckResult(
            passed=False,
            evidence=f".py files contain binary/null bytes: {sample}{more}.",
        )
    return CheckResult(passed=True, evidence="No binary-looking .py files detected.")


# ---- checks: stubware / scaffolding ----------------------------------------


def check_ds7_stubware_density(
    repo_path: Path, max_stub_density: float = 0.80
) -> CheckResult:
    """Fail if ≥80% (default) of functions/methods are stubs (pass/NIE/return None/docstring-only)."""
    stub, total, density = _stub_density(repo_path)
    if total == 0:
        return CheckResult(passed=False, evidence="No functions/methods found.")
    if density >= max_stub_density:
        pct = round(density * 100, 1)
        return CheckResult(
            passed=False,
            evidence=f"Stubware density {pct}% (stubs {stub}/{total}) ≥ {int(max_stub_density*100)}%.",
        )
    pct = round((1.0 - density) * 100, 1)
    return CheckResult(
        passed=True, evidence=f"Non-stub functions ≈ {pct}% (stubs {stub}/{total})."
    )


# ---- checks: mispackaging / empty distribution (static) ---------------------


def check_ds8_no_importable_modules(repo_path: Path) -> CheckResult:
    """Fail if no importable modules/packages exist (no .py files beyond tests/scripts)."""
    code_files = [
        p
        for p in _iter_files(repo_path)
        if not re.search(r"(^|/)tests?(/|$)", str(p).replace("\\", "/"))
    ]
    if not code_files:
        return CheckResult(
            passed=False,
            evidence="No importable modules found (only tests/scripts or nothing).",
        )
    return CheckResult(
        passed=True, evidence=f"Importable module files: {len(code_files)}."
    )


# ---- checks: squatting / name parking via PyPI metadata ---------------------


def check_ds9_name_parking_signals(
    pypi_data: dict | None, stale_days: int = 365
) -> CheckResult:
    """Fail if signals suggest parking: single release, version 0.0.0/0.0.1, and stale > 1 year, and boilerplate summary.
    Requires PyPI JSON for the project (pypi.org/p/<pkg>/json).
    """
    if not pypi_data or "releases" not in pypi_data or "info" not in pypi_data:
        return CheckResult(passed=False, evidence="No PyPI data available.")

    releases = pypi_data.get("releases", {})
    versions = sorted(releases.keys())
    info = pypi_data.get("info", {})
    summary = (info.get("summary") or "").strip().lower()

    # find newest upload time
    newest: Optional[datetime] = None
    for files in releases.values():
        for f in files or []:
            t = f.get("upload_time_iso_8601") or f.get("upload_time")
            if not t:
                continue
            try:
                dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            except Exception:  # nosec
                continue
            if (newest is None) or (dt > newest):
                newest = dt

    now = datetime.now(timezone.utc)
    stale = (newest is None) or ((now - newest).days >= stale_days)
    boilerplate = (not summary) or summary in {
        "todo",
        "test",
        "my package",
        "placeholder",
        "package",
    }
    tiny_version = (
        versions in [["0.0.0"], ["0.0.1"], []]
        or any(v in {"0.0.0", "0.0.1"} for v in versions)
        and len(versions) == 1
    )

    if len(versions) <= 1 and tiny_version and stale and boilerplate:
        msg = [
            f"releases={len(versions)}",
            f"latest={(newest.isoformat() if newest else 'unknown')}",
            f"summary='{summary or 'EMPTY'}'",
            f"versions={versions[:3]}",
        ]
        return CheckResult(
            passed=False, evidence="Name-parking signals: " + ", ".join(msg) + "."
        )
    return CheckResult(
        passed=True,
        evidence=f"Releases={len(versions)}, summary present, not obviously parked.",
    )


# ---- checks: bad/missing metadata ------------------------------------------


def check_ds10_bad_metadata_pyproject(repo_path: Path) -> CheckResult:
    """Fail if pyproject.toml missing core metadata [project].name/version/description."""
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return CheckResult(passed=False, evidence="Missing pyproject.toml.")
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception as e:
        return CheckResult(passed=False, evidence=f"pyproject.toml unreadable: {e}.")

    project = data.get("project") or {}
    missing = [k for k in ("name", "version", "description") if not project.get(k)]
    if missing:
        return CheckResult(
            passed=False, evidence=f"[project] missing: {', '.join(missing)}."
        )
    return CheckResult(
        passed=True, evidence="pyproject.toml has name/version/description."
    )


# ---- checks: pointless / redundant content ---------------------------------


def check_ds11_pointless_content(repo_path: Path) -> CheckResult:
    """Fail if every module either:
    - has no defs/classes AND only trivial stdlib imports; or
    - contains only a top-level print of a constant string.
    If at least one module defines a function/class, pass.
    """
    any_defs = False
    pointless_modules = 0
    total_modules = 0

    for p in _iter_files(repo_path):
        total_modules += 1
        mod = _module_ast(p)
        if mod is None:
            # unparsable handled by another check; treat as not-pointless here
            continue
        defs = [n for n in mod.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]  # type: ignore[attr-defined]
        if defs:
            any_defs = True
            continue
        top_imports: Set[str] = set()
        trivial = True
        for n in mod.body:  # type: ignore[attr-defined]
            if isinstance(n, ast.Import):
                for a in n.names:
                    top_imports.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                top_imports.add(n.module.split(".")[0])
            elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):  # type: ignore[attr-defined]
                # detect print("constant")
                if isinstance(n.value.func, ast.Name) and n.value.func.id == "print":
                    args = n.value.args
                    if (
                        len(args) == 1
                        and isinstance(args[0], ast.Constant)
                        and isinstance(args[0].value, str)
                    ):
                        continue  # still trivial
                trivial = False
            elif isinstance(n, ast.Assign):
                # assignment to constant is fine/trivial
                continue
            else:
                trivial = False
        if top_imports and all(m in _STD_LIB_MODULES for m in top_imports) and trivial:
            pointless_modules += 1

    if total_modules == 0:
        return CheckResult(passed=False, evidence="No modules to analyze.")
    if not any_defs and pointless_modules == total_modules:
        return CheckResult(
            passed=False,
            evidence="All modules are trivial: only stdlib imports and/or print of constants; no defs/classes.",
        )
    return CheckResult(
        passed=True,
        evidence=f"Non-trivial modules present ({total_modules - pointless_modules}/{total_modules}).",
    )


# ---- checks: declares deps but never imports them ---------------------------


def check_ds12_declares_deps_but_never_imports(repo_path: Path) -> CheckResult:
    """Fail if [project.dependencies] are declared but none are actually imported anywhere (static name match).
    Maps requirement names to import names via simple normalization (replace '-' with '_').
    """
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return CheckResult(passed=False, evidence="Missing pyproject.toml.")
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception as e:
        return CheckResult(passed=False, evidence=f"pyproject.toml unreadable: {e}.")

    project = data.get("project") or {}
    deps = project.get("dependencies") or []
    if not deps:
        return CheckResult(passed=True, evidence="No declared dependencies.")

    req_names: Set[str] = set()
    for raw in deps:
        # crude parse: split at first space/comparator/; extra markers ignored
        name = re.split(r"[<>=!;\[ ]", raw, 1)[0].strip().lower().replace("-", "_")
        if name:
            req_names.add(name)

    imported = {name.lower() for name in _top_level_imports(repo_path)}

    unused = sorted([r for r in req_names if r not in imported])
    if len(unused) == len(req_names):
        return CheckResult(
            passed=False,
            evidence=f"None of the declared deps are imported: {', '.join(sorted(req_names))}.",
        )
    elif unused:
        return CheckResult(
            passed=True,
            evidence=f"Some declared deps unused (not imported): {', '.join(unused)}.",
        )
    return CheckResult(
        passed=True,
        evidence="All declared deps are imported somewhere (by name heuristic).",
    )
