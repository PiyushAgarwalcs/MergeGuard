# Shared data contracts for deterministic dataset templates.
# Category patterns separate source snippets from their rendering logic.

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryPattern:
    """Source replacement choices and labels for one seeded category."""

    category: str
    sample_repo: str
    file: str
    severity: str
    before: str
    outputs: tuple[str, ...]
    quotes: tuple[str, ...]
    explanation: str
    suggestion: str
    extra_replacements: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SeedTemplate:
    """A single category variant expressed as exact source replacements."""

    case_id: str
    category: str
    sample_repo: str
    file: str
    severity: str
    difficulty: str
    replacements: tuple[tuple[str, str], ...]
    quote: str
    explanation: str
    suggestion: str


@dataclass(frozen=True)
class SeededChange:
    """A rendered template with source text and diff evidence."""

    template: SeedTemplate
    diff: str
    content: str
    line_start: int
    line_end: int
