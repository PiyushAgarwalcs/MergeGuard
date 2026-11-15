# Generates one bounded synthetic security case through the configured model.
# Returned source is validated as text before any dataset record is written.

from __future__ import annotations

import difflib
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from evals.factory.template_types import SeededChange, SeedTemplate
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.llm import ask_for_object
from mergeguard.llm_fake import ScriptedLLM

PROMPT_PATH = Path(__file__).with_name("prompts") / "seed_issue.v1.md"


class SeedIssueOutput(BaseModel):
    """Validated output shape for one generated source modification."""

    model_config = ConfigDict(extra="forbid")

    updated_source: str = Field(min_length=1)
    quote: str = Field(min_length=1)


def generate_seed(
    template: SeedTemplate,
    *,
    difficulty: str,
    client: ScriptedLLM | None = None,
    sample_root: Path = SAMPLE_ROOT,
) -> SeededChange:
    """Generate a single issue and derive its exact diff evidence from text."""
    source_path = sample_root / template.sample_repo / template.file
    original = source_path.read_text(encoding="utf-8")
    prompt = _render_prompt(template, difficulty, original)
    output = ask_for_object(prompt, SeedIssueOutput, "seed_issue", client=client)
    diff = _diff(template.file, original, output.updated_source)
    matching = [
        line
        for hunk in parse_diff(diff)
        for line in hunk.added
        if line.text.strip() == output.quote.strip()
    ]
    if len(matching) != 1:
        raise ValueError("Generated quote must be exactly one added source line.")
    generated_template = replace(
        template,
        case_id=f"llm-sec-{template.category}-v02",
        difficulty=difficulty,
        quote=output.quote,
    )
    change = SeededChange(
        template=generated_template,
        diff=diff,
        content=output.updated_source,
        line_start=matching[0].line_no,
        line_end=matching[0].line_no,
    )
    return change


def _render_prompt(template: SeedTemplate, difficulty: str, source: str) -> str:
    """Insert untrusted source text into the fixed seed-generation instructions."""
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    values = {
        "category": template.category,
        "difficulty": difficulty,
        "file": template.file,
        "source": source,
    }
    for name, value in values.items():
        prompt = prompt.replace("{{" + name + "}}", value)
    return prompt


def _diff(file: str, original: str, updated: str) -> str:
    """Render one standard unified diff from original and generated text."""
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{file}",
        tofile=f"b/{file}",
        n=3,
    )
    return f"diff --git a/{file} b/{file}\n" + "".join(lines)
