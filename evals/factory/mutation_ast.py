# AST-guided source mutation for correctness seed generation.
# Only a selected expression or statement is replaced in the original text.

from __future__ import annotations

import ast
from dataclasses import dataclass

from evals.factory.mutation_types import MutationSpec


@dataclass(frozen=True)
class SourceEdit:
    """One source range and its replacement text."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int
    replacement: str


class MutationTransformer(ast.NodeTransformer):
    """Find one requested AST node and record its source replacement."""

    def __init__(self, spec: MutationSpec) -> None:
        """Set the target function and node replacement."""
        self.spec = spec
        self.function_name = ""
        self.edit: SourceEdit | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        """Visit a function while tracking its name."""
        previous = self.function_name
        self.function_name = node.name
        result = self.generic_visit(node)
        self.function_name = previous
        return result

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        """Visit an async function while tracking its name."""
        previous = self.function_name
        self.function_name = node.name
        result = self.generic_visit(node)
        self.function_name = previous
        return result

    def visit(self, node: ast.AST) -> ast.AST:
        """Replace the first matching expression or continue statement."""
        if (
            self.function_name == self.spec.function_name
            and self.spec.operation == "expression"
            and isinstance(node, ast.expr)
            and ast.unparse(node) == self.spec.before
        ):
            replacement = ast.parse(self.spec.after, mode="eval").body
            self.edit = _source_edit(node, self.spec.after)
            return ast.copy_location(replacement, node)
        if (
            self.function_name == self.spec.function_name
            and self.spec.operation == "continue"
            and isinstance(node, ast.Continue)
        ):
            replacement = ast.parse(self.spec.after).body[0]
            self.edit = _source_edit(node, self.spec.after)
            return ast.copy_location(replacement, node)
        return super().visit(node)


def _source_edit(node: ast.AST, text: str) -> SourceEdit:
    """Capture a same-line source range for a syntax-tree replacement."""
    end_line = getattr(node, "end_lineno", None)
    end_column = getattr(node, "end_col_offset", None)
    if end_line is None or end_column is None or end_line != node.lineno:
        raise ValueError("Mutation targets must fit on one source line.")
    return SourceEdit(node.lineno, node.col_offset, end_line, end_column, text)


def mutate_source(source: str, spec: MutationSpec) -> tuple[str, SourceEdit]:
    """Apply one AST-selected edit while preserving unrelated source formatting."""
    tree = ast.parse(source)
    transformer = MutationTransformer(spec)
    transformer.visit(tree)
    if transformer.edit is None:
        raise ValueError(f"{spec.case_id}: AST target was not found")
    edit = transformer.edit
    lines = source.splitlines(keepends=True)
    if edit.start_line != edit.end_line:
        raise ValueError(f"{spec.case_id}: mutation must be on one line")
    line = lines[edit.start_line - 1]
    lines[edit.start_line - 1] = (
        line[: edit.start_column] + edit.replacement + line[edit.end_column :]
    )
    updated = "".join(lines)
    ast.parse(updated)
    return updated, edit
