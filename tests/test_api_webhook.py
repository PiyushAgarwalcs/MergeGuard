# Tests webhook authentication, delivery de-duplication and background dispatch.

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path

import httpx

from mergeguard import api, storage
from mergeguard.settings import settings


def _signature(body: bytes, secret: str = "test-secret") -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def _send_requests(requests: list[tuple[bytes, dict[str, str]]]) -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return [
            await client.post("/webhook", content=body, headers=headers)
            for body, headers in requests
        ]


def test_webhook_accepts_once_and_dispatches_in_background(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "webhook.db"))
    monkeypatch.setattr(settings, "MERGEGUARD_WEBHOOK_SECRET", "test-secret")
    delivered: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        api, "WEBHOOK_HANDLER", lambda event, payload: delivered.append((event, payload))
    )
    body = json.dumps({"action": "opened", "number": 7}).encode("utf-8")
    headers = {
        "X-Hub-Signature-256": _signature(body),
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-7",
    }

    accepted, duplicate = asyncio.run(_send_requests([(body, headers), (body, headers)]))

    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert duplicate.json()["duplicate"] is True
    assert delivered == [("pull_request", {"action": "opened", "number": 7})]


def test_webhook_rejects_bad_or_missing_signatures_and_delivery_id(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "MERGEGUARD_WEBHOOK_SECRET", "test-secret")
    body = b'{"action":"opened"}'
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "id"}
    missing, invalid, no_delivery = asyncio.run(
        _send_requests(
            [
                (body, headers),
                (body, {**headers, "X-Hub-Signature-256": "sha256=invalid"}),
                (
                    body,
                    {"X-Hub-Signature-256": _signature(body), "X-GitHub-Event": "pull_request"},
                ),
            ]
        )
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert no_delivery.status_code == 400


def test_webhook_ignores_unsupported_events_and_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MERGEGUARD_WEBHOOK_SECRET", "test-secret")
    body = b'{"action":"ignored"}'
    bad_body = b"not-json"
    unsupported, invalid_json = asyncio.run(
        _send_requests(
            [
                (
                    body,
                    {
                        "X-Hub-Signature-256": _signature(body),
                        "X-GitHub-Event": "push",
                        "X-GitHub-Delivery": "push-1",
                    },
                ),
                (
                    bad_body,
                    {
                        "X-Hub-Signature-256": _signature(bad_body),
                        "X-GitHub-Event": "pull_request",
                        "X-GitHub-Delivery": "invalid-json",
                    },
                ),
            ]
        )
    )

    assert unsupported.status_code == 200
    assert unsupported.json()["ignored"] is True
    assert invalid_json.status_code == 400
