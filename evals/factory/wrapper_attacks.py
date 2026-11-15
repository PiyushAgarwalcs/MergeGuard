# Fabricated verifier inputs derived from genuine seeded findings.
# Every attack uses an exact base diff and a known rejection reason.

from __future__ import annotations

import re
from pathlib import Path

from evals.factory.template_types import SeededChange
from evals.factory.templates import SAMPLE_ROOT, generate_all_seeds
from evals.factory.wrapper_types import VerifierAttack
from mergeguard.models import Finding, ReviewContext, Severity, Source

NEW_LINE = re.compile(r"\+(\d+)")


def generate_verifier_attacks(
    seeds: list[SeededChange] | None = None,
    sample_root: Path = SAMPLE_ROOT,
) -> list[VerifierAttack]:
    """Create four rejected evidence attacks for each real seeded finding."""
    if seeds is None:
        seeds = generate_all_seeds(sample_root)
    attacks: list[VerifierAttack] = []
    for seed in seeds:
        genuine = _finding_for_seed(seed)
        attacks.extend(_attacks_for_seed(seed, genuine))
    return attacks


def finding_for_seed(seed: SeededChange) -> Finding:
    """Create the exact genuine finding represented by one template seed."""
    return _finding_for_seed(seed)


def _attacks_for_seed(seed: SeededChange, genuine: Finding) -> list[VerifierAttack]:
    """Build fabricated quote, line, evidence and unchanged-context findings."""
    context_line = _unchanged_context(seed.diff, seed.template.file)
    wrong_quote = genuine.model_copy(update={"quote": "fabricated evidence marker"})
    wrong_lines = genuine.model_copy(
        update={
            "line_start": genuine.line_end + 100,
            "line_end": genuine.line_end + 100,
        }
    )
    invented_evidence = genuine.model_copy(update={"evidence": ["invented-evidence-id"]})
    unchanged_context = genuine.model_copy(
        update={
            "line_start": context_line[0],
            "line_end": context_line[0],
            "quote": context_line[1],
        }
    )
    attacks = (
        ("fabricated_quote", wrong_quote, "QUOTE_NOT_IN_DIFF", None),
        ("wrong_lines", wrong_lines, "LINES_OUT_OF_RANGE", None),
        (
            "invented_evidence",
            invented_evidence,
            "UNKNOWN_EVIDENCE",
            ReviewContext(blocks=[]),
        ),
        ("unchanged_context", unchanged_context, "QUOTE_NOT_IN_DIFF", None),
    )
    return [
        VerifierAttack(
            case_id=f"verifier-{attack}-{seed.template.case_id}",
            base_case_id=seed.template.case_id,
            attack=attack,
            diff=seed.diff,
            finding=finding,
            expected_rejection=reason,
            context=context,
        )
        for attack, finding, reason, context in attacks
    ]


def _finding_for_seed(seed: SeededChange) -> Finding:
    """Map known template labels into the verifier's finding contract."""
    return Finding(
        id=f"seed-{seed.template.case_id}",
        source=Source.SECURITY,
        category=seed.template.category,
        severity=Severity(seed.template.severity),
        file=seed.template.file,
        line_start=seed.line_start,
        line_end=seed.line_end,
        quote=seed.template.quote,
        explanation="Seeded test finding.",
        suggestion="Replace the unsafe pattern.",
    )


def _unchanged_context(diff: str, target_file: str) -> tuple[int, str]:
    """Choose one unchanged hunk line that is not duplicated as added text."""
    current_file = ""
    new_line = 1
    added_text: list[str] = []
    context_candidates: list[tuple[int, str]] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current_file = line[4:]
            if current_file.startswith(("a/", "b/")):
                current_file = current_file[2:]
            continue
        if line.startswith("@@"):
            match = NEW_LINE.search(line)
            if match:
                new_line = int(match.group(1))
            continue
        if current_file != target_file or line.startswith(("--- ", "diff --git ")):
            continue
        if line.startswith("+"):
            added_text.append(line[1:])
            new_line += 1
        elif line.startswith(" "):
            text = line[1:].strip()
            if text:
                context_candidates.append((new_line, text))
            new_line += 1
    added = " ".join(" ".join(added_text).split())
    for line_number, quote in context_candidates:
        if " ".join(quote.split()) not in added:
            return line_number, quote
    raise ValueError(f"No unchanged context line is available in {target_file}.")
