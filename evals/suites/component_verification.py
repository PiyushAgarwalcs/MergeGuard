# L1 verifier and webhook authentication evaluations.
# Real and fabricated findings are reconstructed from immutable dataset labels.

from __future__ import annotations

import hashlib
import hmac
import sqlite3

from evals.results import SuiteCaseResult
from evals.suites.dataset_cases import load_cases
from mergeguard.api import accept_webhook_delivery, verify_webhook_signature
from mergeguard.checks.verify_findings import verify_findings
from mergeguard.models import Finding, Severity, Source


def evaluate_verifier(
    version: str = "v0.1", split: str | None = None, limit: int | None = None
) -> tuple[float, float, list[SuiteCaseResult]]:
    """Measure fabricated attack acceptance and genuine finding rejection."""
    attack_count = 0
    accepted = 0
    genuine = 0
    rejected_genuine = 0
    results = []
    all_cases = load_cases(version, split)
    attack_cases = [item for item in all_cases if item[0]["source"] == "verifier_attack"]
    genuine_cases = [item for item in all_cases if item[0]["source"] == "seeded"]
    if limit is not None:
        attack_cases = attack_cases[:limit]
        genuine_cases = genuine_cases[:limit]
    for record, diff in attack_cases + genuine_cases:
        source = record["source"]
        if source == "verifier_attack":
            attack_count += 1
            finding = _finding(
                record["findings"][0], evidence=record.get("attack") == "invented_evidence"
            )
            valid, rejected = verify_findings([finding], diff)
            actual_reason = rejected[0].reason if rejected else "ACCEPTED"
            passed = actual_reason == record["expected_rejection"] and not valid
            accepted += not rejected
            results.append(
                SuiteCaseResult(
                    f"l1-verifier-{record['id']}",
                    1,
                    passed,
                    {"rejection": record["expected_rejection"]},
                    {"rejection": actual_reason},
                    {"component": "verifier", "kind": "fabricated"},
                )
            )
        elif source == "seeded":
            for finding_data in record["findings"]:
                genuine += 1
                finding = _finding(finding_data)
                valid, rejected = verify_findings([finding], diff)
                rejected_genuine += bool(rejected)
                results.append(
                    SuiteCaseResult(
                        f"l1-verifier-{record['id']}",
                        1,
                        bool(valid) and not rejected,
                        {"genuine": True},
                        {
                            "accepted": bool(valid),
                            "rejection": rejected[0].reason if rejected else None,
                        },
                        {"component": "verifier", "kind": "genuine"},
                    )
                )
    if not attack_count or not genuine:
        raise ValueError("Verifier suite needs both fabricated and genuine findings.")
    return accepted / attack_count, rejected_genuine / genuine, results


def evaluate_webhook_signature(
    connection: sqlite3.Connection,
) -> tuple[float, list[SuiteCaseResult]]:
    """Check valid, invalid, missing and replayed webhook deliveries."""
    body = b'{"action":"opened"}'
    secret = "mergeguard-test-secret"
    signature = _signature(body, secret)
    valid = verify_webhook_signature(body, signature, secret)
    invalid = verify_webhook_signature(body, "sha256=invalid", secret)
    missing = verify_webhook_signature(body, None, secret)
    results = [
        SuiteCaseResult(
            "l1-webhook-valid-signature", 1, valid, {"accepted": True}, {"accepted": valid}
        ),
        SuiteCaseResult(
            "l1-webhook-invalid-signature",
            1,
            not invalid,
            {"accepted": False},
            {"accepted": invalid},
        ),
        SuiteCaseResult(
            "l1-webhook-missing-signature",
            1,
            not missing,
            {"accepted": False},
            {"accepted": missing},
        ),
    ]
    first, replay = verify_delivery_lifecycle(connection)
    results.extend(
        [
            SuiteCaseResult(
                "l1-webhook-first-delivery", 1, first, {"accepted": True}, {"accepted": first}
            ),
            SuiteCaseResult(
                "l1-webhook-replay", 1, not replay, {"accepted": False}, {"accepted": replay}
            ),
        ]
    )
    return (sum(item.passed for item in results) / len(results), results)


def verify_delivery_lifecycle(connection: sqlite3.Connection) -> tuple[bool, bool]:
    """Accept one valid delivery once and reject a duplicate replay."""
    body = b'{"action":"synchronize"}'
    secret = "mergeguard-test-secret"
    signature = _signature(body, secret)
    first = accept_webhook_delivery(body, signature, secret, "delivery-1", connection=connection)
    replay = accept_webhook_delivery(body, signature, secret, "delivery-1", connection=connection)
    return first, replay


def _finding(data: dict[str, object], evidence: bool = False) -> Finding:
    """Reconstruct a schema-valid finding from its dataset label."""
    return Finding(
        id="L1",
        source=Source.SECURITY,
        category=str(data["category"]),
        severity=Severity(str(data["severity"])),
        file=str(data["file"]),
        line_start=int(data["line_start"]),
        line_end=int(data["line_end"]),
        quote=str(data["quote"]),
        explanation="L1 fixture finding.",
        suggestion="Review the changed code.",
        evidence=["invented-evidence-id"] if evidence else [],
    )


def _signature(body: bytes, secret: str) -> str:
    """Create the signature expected for a local webhook fixture."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
