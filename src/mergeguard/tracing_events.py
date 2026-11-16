# mergeguard.tracing_events
# Persists sanitized structured events and model-call accounting.

from __future__ import annotations

from typing import Any

from mergeguard.settings import settings
from mergeguard.storage import insert_event
from mergeguard.tracing import _hash_text, _log_event, _safe_payload, compute_cost


def record(
    run_id: str,
    node: str,
    kind: str,
    payload: dict[str, Any] | str | None = None,
    *,
    repo: str | None = None,
    pr_number: int | None = None,
    head_sha: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    sanitized_payload = payload if isinstance(payload, str) else _safe_payload(payload)
    event = insert_event(
        run_id,
        node,
        kind,
        sanitized_payload,
        model=model,
        prompt_version=prompt_version,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )
    _log_event(run_id, repo, pr_number, head_sha, event)
    return event


def record_llm_call(
    run_id: str,
    node: str,
    model: str,
    prompt_version: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    output: str,
    *,
    repo: str | None = None,
    pr_number: int | None = None,
    head_sha: str | None = None,
) -> dict[str, Any]:
    cost = compute_cost(model, tokens_in, tokens_out)
    event = insert_event(
        run_id,
        node,
        "llm_call",
        {
            "output": output if not settings.PRIVACY_MODE else _hash_text(output),
            "prompt_version": prompt_version,
        },
        model=model,
        prompt_version=prompt_version,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        latency_ms=latency_ms,
    )
    _log_event(run_id, repo, pr_number, head_sha, event)
    return event
