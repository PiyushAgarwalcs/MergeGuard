# Challenges verified reviewer findings before they affect the decision.
# Rule findings and low-severity findings are never sent to the model.

from __future__ import annotations

import json
from typing import Any

from openai import OpenAIError

from mergeguard import tracing
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.llm import (
    InvalidModelOutput,
    LLMDisabled,
    MissingCredentials,
    ReplayMiss,
    ask_for_object,
    load_prompt,
)
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import (
    Finding,
    Hunk,
    ReviewContext,
    ReviewState,
    Severity,
    SkepticVerdict,
    Source,
)

PROMPT_NAME = "skeptic.v1"
MINIMUM_SEVERITY = {Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL}
LLM_SOURCES = {Source.SECURITY, Source.CORRECTNESS, Source.TESTS}


def run(state: ReviewState, *, client: ScriptedLLM | None = None) -> dict[str, Any]:
    """Review one verified finding against its exact hunk and cited evidence."""
    finding = state.get("finding")
    hunk = state.get("hunk")
    if finding is None or hunk is None:
        return {"verdicts": [], "complete": False}
    if not _eligible(finding):
        return {"verdicts": [], "complete": True}
    context = state.get("context", ReviewContext(ci_status="missing"))
    evidence = [block.model_dump() for block in context.blocks if block.id in finding.evidence]
    prompt = load_prompt(
        PROMPT_NAME,
        finding=json.dumps(finding.model_dump(mode="json"), sort_keys=True),
        hunk=hunk.text,
        evidence=json.dumps(evidence, sort_keys=True, ensure_ascii=False),
    )
    try:
        verdict = ask_for_object(
            prompt,
            SkepticVerdict,
            agent="skeptic",
            client=client,
            run_id=state.get("run_id"),
        )
        if verdict.finding_id != finding.id:
            raise InvalidModelOutput(
                "Skeptic verdict finding_id does not match the reviewed finding."
            )
    except (
        InvalidModelOutput,
        LLMDisabled,
        MissingCredentials,
        OpenAIError,
        ReplayMiss,
        TimeoutError,
    ) as error:
        tracing.record(
            state.get("run_id", "llm-unscoped"),
            "skeptic",
            "agent_failed",
            {"error_type": type(error).__name__},
        )
        return {"verdicts": [], "complete": False}
    return {"verdicts": [verdict], "complete": True}


def review_verified_findings(
    findings: list[Finding],
    diff: str,
    context: ReviewContext,
    *,
    run_id: str | None = None,
    client: ScriptedLLM | None = None,
) -> dict[str, Any]:
    """Run the skeptic only for verified LLM findings of medium severity or higher."""
    verdicts: list[SkepticVerdict] = []
    complete = True
    for finding in findings:
        if not _eligible(finding):
            continue
        hunk = _hunk_for_finding(finding, diff)
        if hunk is None:
            complete = False
            continue
        result = run(
            {
                "finding": finding,
                "hunk": hunk,
                "context": context,
                "run_id": run_id or "llm-unscoped",
            },
            client=client,
        )
        verdicts.extend(result["verdicts"])
        complete = complete and result["complete"]
    return {"verdicts": verdicts, "complete": complete}


def _eligible(finding: Finding) -> bool:
    """Allow only verified LLM sources with medium, high or critical severity."""
    return (
        finding.source in LLM_SOURCES and finding.severity in MINIMUM_SEVERITY and bool(finding.id)
    )


def _hunk_for_finding(finding: Finding, diff: str) -> Hunk | None:
    """Find the single changed hunk containing a finding's file and line range."""
    return next(
        (
            hunk
            for hunk in parse_diff(diff)
            if hunk.file == finding.file
            and hunk.new_start <= finding.line_start <= finding.line_end <= hunk.new_end
        ),
        None,
    )
