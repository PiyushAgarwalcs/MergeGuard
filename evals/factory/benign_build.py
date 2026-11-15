# Shared text-only rendering for generated benign examples.
# No generated source is imported or executed during case construction.

from __future__ import annotations

import difflib
from pathlib import Path

from evals.factory.benign_types import ExampleCase
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff


def append_content(original: str, addition: str) -> str:
    """Append a code or test snippet without changing existing lines."""
    return f"{original.rstrip()}\n\n{addition.rstrip()}\n"


def replace_once(original: str, before: str, after: str) -> str:
    """Replace one exact source fragment or reject a stale case definition."""
    if original.count(before) != 1:
        raise ValueError(f"Expected one occurrence of {before!r}.")
    return original.replace(before, after, 1)


def build_case(
    case_id: str,
    source: str,
    category: str,
    kind: str,
    sample_repo: str,
    edits: tuple[tuple[str, str], ...],
    primary_file: str,
    quote: str,
    expected_decision: str,
    sample_root: Path = SAMPLE_ROOT,
) -> ExampleCase:
    """Render a multi-file case with exact diff-line evidence."""
    patches: list[tuple[str, str]] = []
    changes: list[tuple[str, str]] = []
    for file, updated in edits:
        original = (sample_root / sample_repo / file).read_text(encoding="utf-8")
        if original == updated:
            raise ValueError(f"{case_id}: update for {file} made no change")
        diff_lines = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{file}",
            tofile=f"b/{file}",
            n=3,
        )
        patch = f"diff --git a/{file} b/{file}\n" + "".join(diff_lines)
        patches.append((file, patch))
        changes.append((file, updated))

    diff = "".join(patch for _, patch in patches)
    evidence = [
        line.line_no
        for hunk in parse_diff(diff)
        if hunk.file == primary_file
        for line in hunk.added
        if quote in line.text
    ]
    if not evidence:
        raise ValueError(f"{case_id}: quote is not on an added diff line")
    content_by_file = dict(changes)
    return ExampleCase(
        case_id=case_id,
        source=source,
        category=category,
        kind=kind,
        sample_repo=sample_repo,
        file=primary_file,
        diff=diff,
        content=content_by_file[primary_file],
        quote=quote,
        line_start=min(evidence),
        line_end=max(evidence),
        expected_decision=expected_decision,
        patches=tuple(patches),
        changes=tuple(changes),
    )
