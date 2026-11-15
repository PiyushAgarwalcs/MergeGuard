# Builds bounded repository context for changed Python files.

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from mergeguard.models import ContextBlock, ReviewContext, ReviewState

MAX_CONTEXT_BLOCKS = 40
MAX_BLOCK_CHARS = 1600
MAX_CONTEXT_CHARS = 12000
_FUNCTION_DEF = re.compile(r"^\s*\+\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")


def collect_context(
    repo_root: Path,
    changed_files: Iterable[str],
    diff: str = "",
    ci_status: Literal["passing", "failing", "missing"] | None = None,
) -> ReviewContext:
    """Collect callers, related tests and siblings from a repository snapshot."""
    files = sorted({_safe_repo_path(path) for path in changed_files})
    test_files = [path for path in files if _is_test_file(path)]
    source_files = [path for path in files if path.endswith(".py") and path not in test_files]
    modules = {_module_name(path) for path in source_files}
    changed_functions = _changed_function_names(diff)
    blocks: list[ContextBlock] = []

    for relative in source_files:
        source = _read_repo_file(repo_root, relative)
        if source is None:
            continue
        tree = _parse(source)
        if tree is None:
            continue
        for node in _function_nodes(tree):
            if node.name in changed_functions:
                siblings = [item for item in _function_nodes(tree) if item.name != node.name]
                for sibling in siblings:
                    _append_block(
                        blocks,
                        "sibling",
                        relative,
                        _node_text(source, sibling),
                    )
                break

    for relative in _iter_python_files(repo_root):
        source = _read_repo_file(repo_root, relative)
        if source is None:
            continue
        tree = _parse(source)
        if tree is None:
            continue
        if _is_test_file(relative):
            if _mentions_modules(source, tree, modules):
                _append_block(blocks, "test", relative, source)
            continue
        for node in _function_nodes(tree):
            calls_changed = any(
                isinstance(child, ast.Name) and child.id in changed_functions
                for child in ast.walk(node)
            )
            if relative not in source_files and calls_changed:
                _append_block(blocks, "caller", relative, _node_text(source, node))

    status: Literal["passing", "failing", "missing"] = (
        ci_status if ci_status in {"passing", "failing"} else "missing"
    )
    if status != "missing":
        _append_block(blocks, "ci", "CI", f"CI status: {status}")
    return ReviewContext(
        blocks=blocks,
        ci_status=status,
        changed_source_files=source_files,
        changed_test_files=test_files,
    )


def run(state: ReviewState) -> dict[str, ReviewContext]:
    """Collect context for a PR payload and optional local snapshot path."""
    pr = state.get("pr")
    if pr is None:
        return {"context": ReviewContext(ci_status="missing")}
    root = Path(state.get("repo_path", "."))
    ci_status = state.get("ci_status")
    return {"context": collect_context(root, pr.files, pr.diff, ci_status)}


def _safe_repo_path(path: str) -> str:
    raw = path.replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"Changed path must be relative to the repository: {path!r}")
    normalized = raw
    parts = Path(normalized).parts
    if not normalized or Path(normalized).is_absolute() or ".." in parts:
        raise ValueError(f"Changed path must be relative to the repository: {path!r}")
    return normalized


def _read_repo_file(root: Path, relative: str) -> str | None:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _iter_python_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*.py") if ".git" not in path.parts
    )


def _parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _changed_function_names(diff: str) -> set[str]:
    return {match.group(1) for line in diff.splitlines() if (match := _FUNCTION_DEF.match(line))}


def _module_name(path: str) -> str:
    return path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    parts = Path(path).parts
    return (
        path.startswith(("tests/", "test/"))
        or any(part.endswith("_tests") for part in parts[:-1])
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _mentions_modules(source: str, tree: ast.Module, modules: set[str]) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name in modules or any(module.startswith(alias.name + ".") for module in modules)
            for alias in node.names
        ):
            return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (
                node.module in modules
                or any(module.startswith(node.module + ".") for module in modules)
            )
        ):
            return True
    return any(module in source for module in modules)


def _node_text(source: str, node: ast.AST) -> str:
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


def _append_block(
    blocks: list[ContextBlock],
    kind: Literal["caller", "test", "sibling", "ci", "config"],
    path: str,
    text: str,
) -> None:
    if not text.strip() or len(blocks) >= MAX_CONTEXT_BLOCKS:
        return
    remaining = MAX_CONTEXT_CHARS - sum(len(block.text) for block in blocks)
    clipped = text[: min(MAX_BLOCK_CHARS, remaining)]
    if not clipped.strip():
        return
    blocks.append(ContextBlock(id=f"C-{len(blocks) + 1}", kind=kind, path=path, text=clipped))
