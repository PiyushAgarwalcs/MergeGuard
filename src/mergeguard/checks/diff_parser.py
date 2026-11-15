# checks/diff_parser.py
# Parses a unified diff into concrete hunks and added lines with stable new-file ranges.

from __future__ import annotations

import re

from mergeguard.models import AddedLine, Hunk, ReviewState


def _normalize_path(value: str) -> str:
    text = value.strip()
    if text.startswith("a/") or text.startswith("b/"):
        return text[2:]
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text in {"/dev/null", ""}:
        return ""
    return text


def _extract_patch_path(raw: str) -> str:
    if raw.startswith("+++ ") or raw.startswith("--- "):
        return _normalize_path(raw[4:])
    return _normalize_path(raw)


def parse_diff(diff_text: str) -> list[Hunk]:
    if not diff_text or not diff_text.strip():
        return []

    hunks: list[Hunk] = []
    current_file = ""
    current_hunk: Hunk | None = None
    current_new_line = 1

    def flush_current_hunk() -> None:
        nonlocal current_hunk, current_new_line
        if current_hunk is not None:
            hunks.append(current_hunk)
            current_hunk = None
            current_new_line = 1

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            flush_current_hunk()
            current_file = ""
            continue
        if line.startswith("--- "):
            maybe = _extract_patch_path(line)
            if maybe and maybe != "/dev/null":
                current_file = maybe
            continue
        if line.startswith("+++ "):
            maybe = _extract_patch_path(line)
            if maybe and maybe != "/dev/null":
                current_file = maybe
            continue
        if line.startswith("rename from "):
            current_file = _extract_patch_path(line[len("rename from ") :])
            continue
        if line.startswith("rename to "):
            current_file = _extract_patch_path(line[len("rename to ") :])
            continue
        if line.startswith("@@"):
            flush_current_hunk()
            match = re.search(r"\+([0-9]+)(?:,([0-9]+))?", line)
            if match is None:
                continue
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            current_new_line = max(start, 1)
            current_hunk = Hunk(
                file=current_file,
                new_start=current_new_line,
                new_end=current_new_line + max(count, 1) - 1,
                text="",
                added=[],
            )
            continue
        if current_hunk is None:
            continue
        if line.startswith("\\ No newline at end of file"):
            continue
        if line.startswith("+"):
            text = line[1:]
            current_hunk.added.append(
                AddedLine(file=current_hunk.file, line_no=current_new_line, text=text)
            )
            current_hunk.text += text + "\n"
            current_new_line += 1
        elif line.startswith(" "):
            text = line[1:]
            current_hunk.text += text + "\n"
            current_new_line += 1
        elif line.startswith("-"):
            continue

    flush_current_hunk()
    return hunks


def run(state: ReviewState) -> dict[str, list[Hunk]]:
    pr = state.get("pr")
    diff_text = pr.diff if pr is not None and hasattr(pr, "diff") else ""
    return {"hunks": parse_diff(diff_text)}
