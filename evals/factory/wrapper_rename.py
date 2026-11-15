# Consistent local-variable renaming for one seeded source variant.
# Token positions preserve strings, comments and all non-renamed formatting.

from __future__ import annotations

import ast
import difflib
import io
import tokenize
from pathlib import Path

from evals.factory.template_types import SeededChange
from evals.factory.templates import SAMPLE_ROOT
from evals.factory.wrapper_types import VariantCase


def build_rename_variant(seed: SeededChange, sample_root: Path = SAMPLE_ROOT) -> VariantCase | None:
    """Rename one shared local variable in both sides of the seeded change."""
    original = (sample_root / seed.template.sample_repo / seed.template.file).read_text(
        encoding="utf-8"
    )
    name = _shared_local_name(original, seed.content, seed.template.quote)
    if name is None:
        return None
    replacement = f"variant_{name}"
    if replacement in _name_tokens(original) or replacement in _name_tokens(seed.content):
        return None
    renamed_original = _replace_name(original, name, replacement)
    renamed_updated = _replace_name(seed.content, name, replacement)
    diff_lines = difflib.unified_diff(
        renamed_original.splitlines(keepends=True),
        renamed_updated.splitlines(keepends=True),
        fromfile=f"a/{seed.template.file}",
        tofile=f"b/{seed.template.file}",
        n=3,
    )
    return VariantCase(
        case_id=f"variant-rename-{seed.template.case_id}",
        variant="rename",
        base_case_ids=(seed.template.case_id,),
        diff=f"diff --git a/{seed.template.file} b/{seed.template.file}\n" + "".join(diff_lines),
        expected_categories=(seed.template.category,),
        expected_files=(seed.template.file,),
        expected_quotes=(seed.template.quote,),
        base_overrides=((seed.template.sample_repo, seed.template.file, renamed_original),),
    )


def _shared_local_name(original: str, updated: str, quote: str) -> str | None:
    """Choose a non-quoted assignment variable that is both read and written."""
    original_names = _names_by_context(original)
    updated_names = _names_by_context(updated)
    candidates = (
        (original_names[0] & original_names[1] & updated_names[0] & updated_names[1])
        - original_names[2]
        - updated_names[2]
    )
    return next(
        (
            name
            for name in sorted(candidates)
            if not name.startswith("_") and not name.isupper() and name not in quote
        ),
        None,
    )


def _names_by_context(source: str) -> tuple[set[str], set[str], set[str]]:
    """Collect assigned, read and non-local identifiers from one module."""
    tree = ast.parse(source)
    stores = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    loads = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    nonlocals = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            nonlocals.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nonlocals.add(node.name)
    return stores, loads, nonlocals


def _name_tokens(source: str) -> set[str]:
    """Return identifiers while ignoring occurrences inside strings/comments."""
    return {
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.NAME
    }


def _replace_name(source: str, name: str, replacement: str) -> str:
    """Replace matching AST name tokens without touching strings or comments."""
    lines = source.splitlines(keepends=True)
    positions = [
        (node.lineno - 1, node.col_offset, node.end_col_offset)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Name) and node.id == name
    ]
    for row, start, end in sorted(positions, reverse=True):
        lines[row] = lines[row][:start] + replacement + lines[row][end:]
    return "".join(lines)
