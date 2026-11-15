# mergeguard.api
# Exposes the FastAPI application and health endpoint for the review service.
# Webhook authentication is a separate helper so its trust checks stay testable.

import hashlib
import hmac
import sqlite3

from fastapi import FastAPI

from mergeguard.storage import insert_delivery

app = FastAPI(title="MergeGuard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Verify a GitHub-style sha256 signature using constant-time comparison."""
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def accept_webhook_delivery(
    body: bytes,
    signature: str | None,
    secret: str,
    delivery_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> bool:
    """Accept a valid, first-seen webhook delivery and reject replays."""
    if not verify_webhook_signature(body, signature, secret):
        return False
    result = insert_delivery(delivery_id, connection=connection)
    return bool(result["inserted"])
