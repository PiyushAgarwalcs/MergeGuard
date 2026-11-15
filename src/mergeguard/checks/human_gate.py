# Parses approver commands, records decisions and pauses/resumes graph runs safely.

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from langgraph.types import Command, interrupt

from mergeguard.checks import judge
from mergeguard.models import Approval, Decision, Finding, ReviewState
from mergeguard.storage import insert_event, insert_feedback

COMMAND_PATTERN = re.compile(
    r"^/mergeguard\s+(?:(approve)|(?:override\s+(.+))|(?:dismiss\s+(F-\d+)\s+(.+)))\s*$",
    re.IGNORECASE,
)


class ApprovalRejected(ValueError):
    """A command failed the repository approval policy or SHA binding."""


@dataclass(frozen=True)
class GateCommand:
    """Parsed and normalized user command."""

    kind: Literal["approve", "override", "dismiss"]
    reason: str = ""
    finding_id: str | None = None


def run(state: ReviewState) -> dict[str, Any]:
    """Interrupt for an explicit human command and apply the validated approval."""
    decision = state.get("decision")
    pr = state.get("pr")
    if decision is None or decision.outcome == "pass":
        return {"approval": None}
    if pr is None:
        return {"approval": None, "incomplete": True}
    findings = cast(list[Finding], state.get("decision_findings", []))
    resume = interrupt(
        {
            "kind": "approval_required",
            "run_id": state.get("run_id", ""),
            "head_sha": pr.head_sha,
            "outcome": decision.outcome,
            "reasons": decision.reasons,
            "finding_ids": [finding.id for finding in findings],
        }
    )
    payload = resume.get("approval", resume) if isinstance(resume, dict) else resume
    approval = Approval.model_validate(payload)
    _validate_approval(approval, state)
    return _apply_approval(approval, state)


def parse_command(text: str) -> GateCommand:
    """Accept exactly one supported MergeGuard command and normalize its fields."""
    match = COMMAND_PATTERN.fullmatch(text.strip())
    if match is None:
        normalized = text.strip().casefold()
        if normalized == "/mergeguard override":
            raise ApprovalRejected("Override requires a reason.")
        if re.fullmatch(r"/mergeguard\s+dismiss\s+f-\d+", normalized):
            raise ApprovalRejected("Dismiss requires a reason.")
        raise ApprovalRejected(
            "Command must be approve, override with a reason, or dismiss F-N with a reason."
        )
    approve, override_reason, finding_id, dismiss_reason = match.groups()
    if approve:
        return GateCommand("approve")
    if override_reason is not None:
        reason = override_reason.strip()
        if not reason:
            raise ApprovalRejected("Override requires a reason.")
        return GateCommand("override", reason=reason)
    reason = (dismiss_reason or "").strip()
    if not reason:
        raise ApprovalRejected("Dismiss requires a reason.")
    return GateCommand("dismiss", reason=reason, finding_id=finding_id.upper())


def load_approvers(repo_path: str | Path) -> set[str]:
    """Read the allow-list from the target repository's .mergeguard.yml."""
    config_path = Path(repo_path) / ".mergeguard.yml"
    if not config_path.is_file():
        return set()
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ApprovalRejected("Could not read the repository approver policy.") from error
    if not isinstance(payload, dict):
        raise ApprovalRejected("Repository policy must be a YAML mapping.")
    approvers = payload.get("approvers", [])
    if not isinstance(approvers, list) or any(not isinstance(name, str) for name in approvers):
        raise ApprovalRejected("The approvers setting must be a list of usernames.")
    return {name.strip().casefold() for name in approvers if name.strip()}


def authorize_command(
    command: GateCommand,
    by_user: str,
    approvers: set[str],
    *,
    head_sha: str,
    decision: Decision,
    findings: list[Finding],
) -> Approval:
    """Check approver, action/outcome, finding id and bind the action to this SHA."""
    if not by_user or by_user.strip().casefold() not in {name.casefold() for name in approvers}:
        raise ApprovalRejected("This GitHub user is not listed as a MergeGuard approver.")
    if command.kind == "approve" and decision.outcome != "needs_human":
        raise ApprovalRejected("Approve applies only to a needs_human decision.")
    if command.kind == "override" and decision.outcome != "block":
        raise ApprovalRejected("Override applies only to a block decision.")
    if command.kind == "dismiss" and not any(
        finding.id == command.finding_id for finding in findings
    ):
        raise ApprovalRejected("Dismiss refers to a finding that is not active in this review.")
    return Approval(
        kind=command.kind,
        by_user=by_user.strip(),
        reason=command.reason,
        head_sha=head_sha,
        finding_id=command.finding_id,
    )


def record_command(
    text: str,
    by_user: str,
    state: ReviewState,
) -> Approval:
    """Parse, authorize, and persist a command before graph resumption."""
    pr = state.get("pr")
    decision = state.get("decision")
    if pr is None or decision is None:
        raise ApprovalRejected("The review checkpoint has no pull request decision.")
    command = parse_command(text)
    findings = cast(list[Finding], state.get("decision_findings", []))
    approval = authorize_command(
        command,
        by_user,
        load_approvers(state.get("repo_path", ".")),
        head_sha=pr.head_sha,
        decision=decision,
        findings=findings,
    )
    run_id = state.get("run_id", "unknown-run")
    insert_feedback(
        run_id,
        approval.finding_id or "",
        approval.kind,
        approval.by_user,
        approval.reason,
    )
    insert_event(
        run_id,
        "human_gate",
        "approval_action",
        {
            "kind": approval.kind,
            "by_user": approval.by_user,
            "reason": approval.reason,
            "head_sha": approval.head_sha,
            "finding_id": approval.finding_id,
        },
    )
    return approval


async def resume_review(graph: Any, thread_id: str, text: str, by_user: str) -> dict[str, Any]:
    """Authorize and persist a comment command, then resume its paused graph thread."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise ApprovalRejected("No saved review checkpoint exists for this thread.")
    approval = record_command(text, by_user, cast(ReviewState, snapshot.values))
    resumed = await graph.ainvoke(
        Command(resume={"approval": approval.model_dump(mode="json")}), config=config
    )
    return cast(dict[str, Any], resumed)


def _validate_approval(approval: Approval, state: ReviewState) -> None:
    """Recheck resumed payloads so direct checkpoint resumes cannot bypass policy."""
    pr = state.get("pr")
    decision = state.get("decision")
    if pr is None or decision is None:
        raise ApprovalRejected("The review checkpoint is missing its decision or head SHA.")
    if approval.head_sha != pr.head_sha:
        raise ApprovalRejected("Approval belongs to a stale pull request head SHA.")
    command = GateCommand(approval.kind, approval.reason, approval.finding_id)
    authorize_command(
        command,
        approval.by_user,
        load_approvers(state.get("repo_path", ".")),
        head_sha=pr.head_sha,
        decision=decision,
        findings=cast(list[Finding], state.get("decision_findings", [])),
    )


def _apply_approval(approval: Approval, state: ReviewState) -> dict[str, Any]:
    """Apply an accepted command to the final decision and reporter inputs."""
    decision = state.get("decision")
    if decision is None:
        raise ApprovalRejected("The review decision is missing.")
    if approval.kind in {"approve", "override"}:
        reason = f"Decision cleared by {approval.by_user}: {approval.reason or 'approved'}"
        return {
            "approval": approval,
            "decision": decision.model_copy(
                update={"outcome": "pass", "reasons": [reason], "complete": True}
            ),
        }
    findings = cast(list[Finding], state.get("decision_findings", []))
    remaining = [finding for finding in findings if finding.id != approval.finding_id]
    updated_state = dict(state)
    updated_state["findings"] = remaining
    updated_state["decision_findings"] = remaining
    updated_state["complete"] = decision.complete
    judged = judge.judge_run(updated_state)
    return {"approval": approval, "decision_findings": remaining, "decision": judged["decision"]}


__all__ = [
    "ApprovalRejected",
    "GateCommand",
    "authorize_command",
    "load_approvers",
    "parse_command",
    "record_command",
    "resume_review",
    "run",
]
