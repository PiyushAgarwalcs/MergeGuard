# Shared contracts for AST mutation cases.
# A mutation keeps its source diff and the test suite failure that validates it.

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationSpec:
    """One AST edit to apply to a sample application's source."""

    case_id: str
    category: str
    sample_repo: str
    file: str
    function_name: str
    operation: str
    before: str
    after: str


@dataclass(frozen=True)
class MutationCase:
    """A test-killed source mutation with exact diff evidence."""

    case_id: str
    category: str
    sample_repo: str
    file: str
    content: str
    diff: str
    quote: str
    line_start: int
    line_end: int
