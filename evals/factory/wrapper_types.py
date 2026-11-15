# Contracts for adversarial wrappers and label-preserving dataset variants.
# Snapshot overrides describe harmless base-tree changes for rename variants.

from dataclasses import dataclass

from mergeguard.models import Finding, ReviewContext


@dataclass(frozen=True)
class InjectionCase:
    """A prompt-injection placement wrapped around one seeded change."""

    case_id: str
    base_case_id: str
    placement: str
    goal: str
    diff: str
    marker: str
    expected_category: str
    expected_file: str
    expected_quote: str
    filename: str | None = None
    commit_message: str = ""
    pr_title: str = ""
    pr_body: str = ""


@dataclass(frozen=True)
class VariantCase:
    """One deterministic representation variant of one or more seed cases."""

    case_id: str
    variant: str
    base_case_ids: tuple[str, ...]
    diff: str
    expected_categories: tuple[str, ...]
    expected_files: tuple[str, ...]
    expected_quotes: tuple[str, ...]
    base_overrides: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class VerifierAttack:
    """A fabricated finding that should be rejected by the verifier."""

    case_id: str
    base_case_id: str
    attack: str
    diff: str
    finding: Finding
    expected_rejection: str
    context: ReviewContext | None = None
