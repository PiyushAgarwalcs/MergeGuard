# Independently checks generated seed labels before they enter the dataset.
# Disagreement is returned to the factory for its review queue.

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from evals.factory.template_types import SeededChange
from mergeguard.llm import ask_for_object
from mergeguard.llm_fake import ScriptedLLM

PROMPT_PATH = Path(__file__).with_name("prompts") / "cross_check.v1.md"


class CrossCheckOutput(BaseModel):
    """Validated independent reviewer response."""

    model_config = ConfigDict(extra="forbid")

    agrees: bool
    category: str
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    reason: str = Field(min_length=1)


def check_seed(seed: SeededChange, client: ScriptedLLM | None = None) -> CrossCheckOutput:
    """Ask the cross-check model to verify the category and exact location."""
    template = seed.template
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    values = {
        "category": template.category,
        "file": template.file,
        "line": str(seed.line_start),
        "diff": seed.diff,
    }
    for name, value in values.items():
        prompt = prompt.replace("{{" + name + "}}", value)
    return ask_for_object(prompt, CrossCheckOutput, "cross_check", client=client)


def agrees_with_seed(seed: SeededChange, result: CrossCheckOutput) -> bool:
    """Require cross-check agreement on category, file and changed line."""
    template = seed.template
    return (
        result.agrees
        and result.category == template.category
        and result.file == template.file
        and result.line_start <= seed.line_start <= result.line_end
    )
