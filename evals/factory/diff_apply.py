# Text-only unified diff application for case validation.
# Context is checked exactly so a patch cannot drift onto a different base.

import re

HUNK_HEADER = re.compile(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")


def apply_unified_diff(original: str, diff: str) -> str:
    """Apply a unified diff to source text, rejecting context mismatches."""
    original_lines = original.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in original else "\n"
    result: list[str] = []
    source_index = 0
    diff_lines = diff.splitlines()
    hunk_indexes = [i for i, line in enumerate(diff_lines) if line.startswith("@@")]
    if not hunk_indexes:
        raise ValueError("Diff contains no hunks.")

    for position, hunk_index in enumerate(hunk_indexes):
        match = HUNK_HEADER.match(diff_lines[hunk_index])
        if match is None:
            raise ValueError("Diff contains an invalid hunk header.")
        target_index = max(int(match.group(1)) - 1, 0)
        if target_index < source_index or target_index > len(original_lines):
            raise ValueError("Diff hunk starts outside the source file.")
        result.extend(original_lines[source_index:target_index])
        source_index = target_index
        end_index = (
            hunk_indexes[position + 1] if position + 1 < len(hunk_indexes) else len(diff_lines)
        )

        for line in diff_lines[hunk_index + 1 : end_index]:
            if line.startswith("\\ No newline"):
                continue
            operation, text = line[:1], line[1:]
            if operation == " ":
                _match_source_line(original_lines, source_index, text)
                result.append(original_lines[source_index])
                source_index += 1
            elif operation == "-":
                _match_source_line(original_lines, source_index, text)
                source_index += 1
            elif operation == "+":
                result.append(text + newline)
            else:
                raise ValueError("Diff contains an invalid hunk line.")
    result.extend(original_lines[source_index:])
    return "".join(result)


def _match_source_line(lines: list[str], index: int, expected: str) -> None:
    """Ensure a context or deletion line matches the original source."""
    if index >= len(lines) or lines[index].rstrip("\r\n") != expected:
        raise ValueError("Diff context does not match the source file.")
