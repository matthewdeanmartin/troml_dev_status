# troml_dev_status/checks_completeness.py
from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Iterable, Iterator

from troml_dev_status.analysis.filesystem import find_src_dir
from troml_dev_status.analysis.iter_the_files import _iter_files, iter_files2
from troml_dev_status.models import CheckResult

logger = logging.getLogger(__name__)
# ---- shared helpers ------------------------------------------------------------


_CODE_EXTS = {".py"}
_DOC_EXTS = {".md", ".rst", ".txt", ""}  # "" -> files like LICENSE, NOTICE, etc.

_TODO_RE = re.compile(r"\b(?:TODO|FIXME|BUG)\b", re.IGNORECASE)

_VENV_NAME_RE = re.compile(r"^(?:\.?venv|\.?env)(?:[-._]?\w+)*$", re.IGNORECASE)


def _read_text(path: Path) -> str:
    try:
        # Read as bytes then decode with fallback to be robust on odd encodings
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _count_nonempty_py_loc(py_files: Iterable[Path]) -> int:
    """
    Counts non-empty, non-whitespace lines across Python files.
    (Simple LOC for the 1kLOC denominator.)
    """
    total = 0
    for f in py_files:
        txt = _read_text(f)
        for line in txt.splitlines():
            if line.strip():
                total += 1
    return total


# ---- Cmpl1: TODO/FIXME/BUG markers --------------------------------------------


def check_cmpl1_todo_density(repo_path: Path) -> CheckResult:
    """
    Count TODO/FIXME/BUG occurrences in code and docs.
    Fail if > 5 markers per 1000 non-empty Python LOC.
    """
    repo_path = find_src_dir(repo_path) or repo_path
    py_files = list(iter_files2(repo_path, _CODE_EXTS))
    doc_files = list(iter_files2(repo_path, _DOC_EXTS))

    loc = _count_nonempty_py_loc(py_files)
    if loc == 0:
        return CheckResult(
            passed=False,
            evidence="No Python code lines found; cannot compute TODO density.",
        )

    markers = 0
    for f in py_files + doc_files:
        txt = _read_text(f)
        markers += len(_TODO_RE.findall(txt))

    per_kloc = markers * 1000 / max(loc, 1)
    passed = per_kloc <= 5.0
    return CheckResult(
        passed=passed,
        evidence=(
            f"{markers} TODO/FIXME/BUG markers across {loc} non-empty Python LOC "
            f"({per_kloc:.2f} per 1k LOC; threshold ≤ 5.00)."
        ),
    )


# ---- AST utilities used by Cmpl2/Cmpl3/Cmpl4 ----------------------------------


def _is_abstract_decorated(func: ast.AST) -> bool:
    """True if function/method has @abstractmethod decorator."""
    if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for dec in func.decorator_list:
        # Covers: @abstractmethod, @abc.abstractmethod, @something.abstractmethod
        if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod":
            return True
    return False


def _class_is_abc(cls: ast.ClassDef) -> bool:
    """True if class bases suggest ABC/ABCMeta."""
    for base in cls.bases:
        # ABC, abc.ABC, ABCMeta, abc.ABCMeta
        if isinstance(base, ast.Name) and base.id in {"ABC", "ABCMeta"}:
            return True
        if isinstance(base, ast.Attribute) and base.attr in {"ABC", "ABCMeta"}:
            return True
    return False


def _function_body_is_single_raise_notimplemented(func: ast.AST) -> bool:
    body = getattr(func, "body", [])
    # allow an optional initial docstring Expr
    stmts = body
    first_line_is_str = False
    first_line = getattr(stmts[0], "value", None)
    if first_line and isinstance(first_line, str):
        first_line_is_str = True
    if (
        stmts
        and isinstance(stmts[0], ast.Expr)
        and isinstance(getattr(stmts[0], "value", None), (ast.Str, ast.Constant))
        and first_line_is_str
    ):  # isinstance(getattr(stmts[0], "value", None).value, str):
        stmts = stmts[1:]
    if len(stmts) != 1 or not isinstance(stmts[0], ast.Raise):
        return False
    exc = stmts[0].exc
    # raise NotImplementedError(...) or raise NotImplementedError
    if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
        return True
    if (
        isinstance(exc, ast.Call)
        and isinstance(exc.func, ast.Name)
        and exc.func.id == "NotImplementedError"
    ):
        return True
    if isinstance(exc, ast.Attribute) and exc.attr == "NotImplementedError":
        return True
    if (
        isinstance(exc, ast.Call)
        and isinstance(exc.func, ast.Attribute)
        and exc.func.attr == "NotImplementedError"
    ):
        return True
    return False


def _function_body_is_only_pass(func: ast.AST) -> bool:
    body = getattr(func, "body", [])
    # allow leading docstring
    stmts = body
    first_line_is_str = False
    if stmts:
        first_line = getattr(stmts[0], "value", None)
        if first_line and isinstance(first_line, str):
            first_line_is_str = True
    if (
        stmts
        and isinstance(stmts[0], ast.Expr)
        and isinstance(getattr(stmts[0], "value", None), (ast.Str, ast.Constant))
        and first_line_is_str
    ):
        stmts = stmts[1:]
    return len(stmts) == 1 and isinstance(stmts[0], ast.Pass)


def _iter_functions(tree: ast.AST) -> Iterator[tuple[ast.AST, ast.ClassDef | None]]:
    """
    Yields (func_node, owning_class_or_None). Counts both free functions and methods.
    """
    class_stack: list[ast.ClassDef] = []

    class V(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
            class_stack.append(node)
            self.generic_visit(node)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
            cls = class_stack[-1] if class_stack else None
            funcs.append((node, cls))

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # type: ignore[override]
            cls = class_stack[-1] if class_stack else None
            funcs.append((node, cls))

    funcs: list[tuple[ast.AST, ast.ClassDef | None]] = []
    V().visit(tree)
    return iter(funcs)


# ---- Cmpl2: NotImplemented usage ----------------------------------------------


def check_cmpl2_notimplemented_ratio(repo_path: Path) -> CheckResult:
    """
    Pass if < 1% of functions/methods raise NotImplementedError.
    Excludes methods decorated with @abstractmethod and methods on ABC classes.
    """
    py_files = list(_iter_files(repo_path, tuple(_CODE_EXTS)))
    total_funcs = 0
    notimpl_funcs = 0

    for f in py_files:
        txt = _read_text(f)
        if not txt.strip():
            continue
        try:
            tree = ast.parse(txt, filename=str(f))
        except SyntaxError:
            continue

        for func, owning_cls in _iter_functions(tree):
            total_funcs += 1

            # whitelist: abstract method or method on ABC/ABCMeta
            if _is_abstract_decorated(func):
                continue
            if owning_cls is not None and _class_is_abc(owning_cls):
                continue

            if _function_body_is_single_raise_notimplemented(func):
                notimpl_funcs += 1

    if total_funcs == 0:
        return CheckResult(
            passed=False,
            evidence="No functions/methods discovered; cannot compute NotImplemented ratio.",
        )

    ratio = notimpl_funcs / total_funcs
    return CheckResult(
        passed=ratio < 0.01,
        evidence=(
            f"{notimpl_funcs}/{total_funcs} functions/methods raise NotImplementedError "
            f"({ratio:.2%}; threshold < 1%)."
        ),
    )


# ---- Cmpl3: Placeholder `pass` in functions/methods ----------------------------


def check_cmpl3_placeholder_pass_ratio(repo_path: Path) -> CheckResult:
    """
    Pass if < 5% of functions/methods consist only of 'pass'.
    Class-level 'pass' is allowed and not counted (we only look at functions/methods).
    """
    py_files = list(_iter_files(repo_path, tuple(_CODE_EXTS)))
    total_funcs = 0
    pass_only = 0

    for f in py_files:
        txt = _read_text(f)
        if not txt.strip():
            continue
        try:
            tree = ast.parse(txt, filename=str(f))
        except SyntaxError:
            continue

        for func, _ in _iter_functions(tree):
            total_funcs += 1
            if _function_body_is_only_pass(func):
                pass_only += 1

    if total_funcs == 0:
        return CheckResult(
            passed=False,
            evidence="No functions/methods discovered; cannot compute placeholder 'pass' ratio.",
        )

    ratio = pass_only / total_funcs
    return CheckResult(
        passed=ratio < 0.05,
        evidence=(
            f"{pass_only}/{total_funcs} functions/methods are 'pass' only "
            f"({ratio:.2%}; threshold < 5%)."
        ),
    )


# ---- Cmpl4: Stub file detection -----------------------------------------------


def _is_stub_file(path: Path) -> bool:
    """
    Heuristics:
      - File has < 10 total non-empty lines, AND
      - AST contains no “meaningful” statements (anything other than:
            module docstring, Pass, Ellipsis, Raise NotImplementedError)
        OR the only top-level definitions are empty classes (single 'pass')
        and empty functions (pass or NotImplementedError).
    """
    if path.name in ("__init__.py", "py.typed"):
        return False

    txt = _read_text(path)
    nonempty_lines = [ln for ln in txt.splitlines() if ln.strip()]
    if len(nonempty_lines) >= 10:
        return False

    try:
        tree = ast.parse(txt, filename=str(path))
    except SyntaxError:
        # very short but unparsable files are effectively stubs
        return True

    # Track whether we see anything "real"
    meaningful = False

    # module docstring?
    module_body = tree.body[:]

    first_line_is_str = False
    if module_body:
        first_line = getattr(module_body[0], "value", None)
        if first_line and isinstance(first_line, str):
            first_line_is_str = True

    if (
        module_body
        and isinstance(module_body[0], ast.Expr)
        and isinstance(getattr(module_body[0], "value", None), (ast.Str, ast.Constant))
        and first_line_is_str
    ):
        module_body = module_body[1:]

    for node in module_body:
        if isinstance(node, ast.Pass):
            continue
        if isinstance(node, ast.Expr) and isinstance(
            getattr(node, "value", None), ast.Ellipsis
        ):
            continue
        if isinstance(node, ast.Raise) and _is_raise_notimplemented(node):
            continue

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _function_body_is_only_pass(
                node
            ) or _function_body_is_single_raise_notimplemented(node):
                continue
            meaningful = True
            break

        if isinstance(node, ast.ClassDef):
            # class with only pass (ignore class docstring)
            body = node.body

            first_line_is_str = False
            if body:
                first_line = getattr(body[0], "value", None)
                if first_line and isinstance(first_line, str):
                    first_line_is_str = True

            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), (ast.Str, ast.Constant))
                and first_line_is_str
            ):
                body = body[1:]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                continue
            # non-empty class contents are meaningful
            meaningful = True
            break

        # any other top-level node is meaningful (imports, assignments, etc.)
        meaningful = True
        break

    return not meaningful


def _is_raise_notimplemented(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
        return True
    if (
        isinstance(exc, ast.Call)
        and isinstance(exc.func, ast.Name)
        and exc.func.id == "NotImplementedError"
    ):
        return True
    if isinstance(exc, ast.Attribute) and exc.attr == "NotImplementedError":
        return True
    if (
        isinstance(exc, ast.Call)
        and isinstance(exc.func, ast.Attribute)
        and exc.func.attr == "NotImplementedError"
    ):
        return True
    return False


def check_cmpl4_stub_files_ratio(repo_path: Path) -> CheckResult:
    """
    Fail if > 10% of discovered .py files are “stub files” per _is_stub_file.
    """
    py_files = list(_iter_files(repo_path, tuple(_CODE_EXTS)))
    if not py_files:
        return CheckResult(passed=False, evidence="No Python files discovered.")

    stub_count = sum(1 for f in py_files if _is_stub_file(f))
    ratio = stub_count / len(py_files)
    return CheckResult(
        passed=ratio <= 0.10,
        evidence=(
            f"{stub_count}/{len(py_files)} Python files classified as stubs "
            f"({ratio:.2%}; threshold ≤ 10%)."
        ),
    )
