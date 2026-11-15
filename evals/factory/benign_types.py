# Shared case shape for benign and test-gap dataset examples.
# Generated diffs retain the exact content and patch for each changed file.

from dataclasses import dataclass


@dataclass(frozen=True)
class ExampleCase:
    """One deterministic benign or test-gap pull request example."""

    case_id: str
    source: str
    category: str
    kind: str
    sample_repo: str
    file: str
    diff: str
    content: str
    quote: str
    line_start: int
    line_end: int
    expected_decision: str
    patches: tuple[tuple[str, str], ...]
    changes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CaseValidation:
    """Mechanical validation results for one generated example."""

    case_id: str
    passed: tuple[str, ...]
    failures: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Report whether all required checks passed."""
        return not self.failures
