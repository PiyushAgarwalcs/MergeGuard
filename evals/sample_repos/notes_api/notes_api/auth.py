# Authorization helpers for the sample notes service.
# Notes are always scoped to the authenticated user.

import hmac


def is_authorized(provided_token: str, expected_token: str) -> bool:
    """Compare API tokens without leaking match position."""
    if not expected_token:
        return False
    return hmac.compare_digest(provided_token.encode(), expected_token.encode())


def require_user(user_id: str | None) -> str:
    """Return a valid user id or raise a permission error."""
    if user_id is None or not user_id.strip():
        raise PermissionError("An authenticated user is required.")
    return user_id
