# Deterministic label-preserving variants of generated security seeds.
# Base overrides are limited to the renamed source file for one variant.

from __future__ import annotations

import difflib
from pathlib import Path

from evals.factory.template_types import SeededChange
from evals.factory.templates import SAMPLE_ROOT, generate_all_seeds
from evals.factory.wrapper_rename import build_rename_variant
from evals.factory.wrapper_types import VariantCase


def generate_variants(
    seeds: list[SeededChange] | None = None,
    sample_root: Path = SAMPLE_ROOT,
) -> list[VariantCase]:
    """Return comment, CRLF, rename and reordered-file variants."""
    if seeds is None:
        seeds = generate_all_seeds(sample_root)
    if not seeds:
        raise ValueError("Variants require at least one base seed.")

    variants: list[VariantCase] = []
    for seed in seeds:
        variants.append(_comment_variant(seed, sample_root))
        variants.append(_reformat_variant(seed))
        renamed = build_rename_variant(seed, sample_root)
        if renamed is not None:
            variants.append(renamed)

    reordered = _reordered_variant(seeds)
    if reordered is not None:
        variants.append(reordered)
    return variants


def _comment_variant(seed: SeededChange, sample_root: Path) -> VariantCase:
    """Add an inert source comment without changing the seeded finding."""
    original = _original(seed, sample_root)
    updated = f"{seed.content.rstrip()}\n\n# Harmless formatting variant.\n"
    diff = _render_diff(seed.template.file, original, updated)
    return VariantCase(
        case_id=f"variant-comment-{seed.template.case_id}",
        variant="harmless_comment",
        base_case_ids=(seed.template.case_id,),
        diff=diff,
        expected_categories=(seed.template.category,),
        expected_files=(seed.template.file,),
        expected_quotes=(seed.template.quote,),
    )


def _reformat_variant(seed: SeededChange) -> VariantCase:
    """Change only diff line endings to exercise equivalent formatting."""
    return VariantCase(
        case_id=f"variant-crlf-{seed.template.case_id}",
        variant="reformat",
        base_case_ids=(seed.template.case_id,),
        diff=seed.diff.replace("\n", "\r\n"),
        expected_categories=(seed.template.category,),
        expected_files=(seed.template.file,),
        expected_quotes=(seed.template.quote,),
    )


def _reordered_variant(seeds: list[SeededChange]) -> VariantCase | None:
    """Reverse two independent file patches while retaining both labels."""
    for left_index, left in enumerate(seeds):
        for right in seeds[left_index + 1 :]:
            if (
                left.template.sample_repo == right.template.sample_repo
                and left.template.file != right.template.file
            ):
                return VariantCase(
                    case_id=f"variant-reordered-{left.template.case_id}-{right.template.case_id}",
                    variant="reordered",
                    base_case_ids=(right.template.case_id, left.template.case_id),
                    diff=right.diff + left.diff,
                    expected_categories=(right.template.category, left.template.category),
                    expected_files=(right.template.file, left.template.file),
                    expected_quotes=(right.template.quote, left.template.quote),
                )
    return None


def _original(seed: SeededChange, sample_root: Path) -> str:
    """Read the exact base file used by the template."""
    return (sample_root / seed.template.sample_repo / seed.template.file).read_text(
        encoding="utf-8"
    )


def _render_diff(file: str, original: str, updated: str) -> str:
    """Render one changed file as a unified diff."""
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{file}",
        tofile=f"b/{file}",
        n=3,
    )
    return f"diff --git a/{file} b/{file}\n" + "".join(lines)
