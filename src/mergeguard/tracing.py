# mergeguard.tracing
# Records LLM and system events so runs can be reconstructed from the SQLite store.

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from mergeguard.checks.redact import redact_diff
from mergeguard.settings import settings
from mergeguard.storage import insert_event

logger = logging.getLogger("mergeguard.tracing")


def _utciso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_text(value: str, *, key: str | None = None) -> str:
    if settings.PRIVACY_MODE and (key is None or key.lower() == "diff"):
        return _hash_text(value)
    if key is not None and key.lower() == "diff":
        return redact_diff(value)
    return value


def _safe_payload(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, str):
        return _safe_text(value, key=key)
    if isinstance(value, dict):
        return {str(k): _safe_payload(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_safe_payload(item, key=key) for item in value]
    return value


def _serialize_payload(payload: Any) -> str:
    if payload is None:
        return json.dumps({"value": None}, sort_keys=True)
    safe = _safe_payload(payload)
    if isinstance(safe, str):
        return json.dumps({"value": safe}, sort_keys=True)
    return json.dumps(safe, sort_keys=True, default=str)


def _load_prices() -> dict[str, dict[str, float]]:
    prices_path = Path("config/prices.yml")
    if not prices_path.exists():
        return {}
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(prices_path.read_text(encoding="utf-8")) or {}
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return {}
    prices = data.get("prices") if isinstance(data, dict) else {}
    if not isinstance(prices, dict):
        return {}
    normalized: dict[str, dict[str, float]] = {}
    for model_name, values in prices.items():
        if not isinstance(values, dict):
            continue
        normalized[str(model_name)] = {
            "input_per_1k": float(values.get("input_per_1k", 0.0)),
            "output_per_1k": float(values.get("output_per_1k", 0.0)),
        }
    return normalized


def compute_cost(model: str | None, tokens_in: int | None, tokens_out: int | None) -> float:
    if model is None or tokens_in is None or tokens_out is None:
        return 0.0
    prices = _load_prices().get(model, {})
    input_rate = float(prices.get("input_per_1k", 0.0))
    output_rate = float(prices.get("output_per_1k", 0.0))
    if input_rate == 0 and output_rate == 0:
        return 0.0
    return (tokens_in / 1000.0) * input_rate + (tokens_out / 1000.0) * output_rate


def _log_event(
    run_id: str,
    repo: str | None,
    pr_number: int | None,
    head_sha: str | None,
    event: dict[str, Any],
) -> None:
    payload = {
        "run_id": run_id,
        "repo": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        **event,
    }
    logger.info(json.dumps(_safe_payload(payload), sort_keys=True, default=str))


@contextmanager
def span(
    run_id: str,
    node: str,
    *,
    repo: str | None = None,
    pr_number: int | None = None,
    head_sha: str | None = None,
    **meta: Any,
) -> Iterator[dict[str, Any]]:
    started = perf_counter()
    start_payload = {"phase": "start", **meta}
    record(run_id, node, "span", start_payload, repo=repo, pr_number=pr_number, head_sha=head_sha)
    try:
        yield {"run_id": run_id, "node": node, "started_at": _utciso()}
    except Exception as exc:  # pragma: no cover - re-raises after recording the error
        elapsed_ms = int((perf_counter() - started) * 1000)
        record(
            run_id,
            node,
            "error",
            {"phase": "end", "error": str(exc), **meta},
            repo=repo,
            pr_number=pr_number,
            head_sha=head_sha,
        )
        raise
    else:
        elapsed_ms = int((perf_counter() - started) * 1000)
        record(
            run_id,
            node,
            "span",
            {"phase": "end", "duration_ms": elapsed_ms, **meta},
            repo=repo,
            pr_number=pr_number,
            head_sha=head_sha,
        )


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


def trace(event: str, **payload: Any) -> dict[str, Any]:
    return {"event": event, **payload}


__all__ = [
    "compute_cost",
    "record",
    "record_llm_call",
    "span",
    "trace",
]
