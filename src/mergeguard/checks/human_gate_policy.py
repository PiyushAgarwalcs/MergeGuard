# mergeguard.checks.human_gate_policy
# Parses approver commands and enforces repository authorization rules.

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from mergeguard.models import Approval, Decision, Finding

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
