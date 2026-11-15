# URL-shortening business rules and code generation.
# Codes are random and checked for collisions before insertion.

import secrets
import sqlite3
import string

from shortener import store
from shortener.config import is_http_url

CODE_LENGTH = 8
CODE_ALPHABET = string.ascii_letters + string.digits


def _new_code() -> str:
    """Generate an opaque code from URL-safe alphanumeric characters."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def shorten(database_path: str, destination: str, owner: str) -> str:
    """Validate a destination and save a new shortened mapping."""
    if not is_http_url(destination):
        raise ValueError("Destination must be an absolute HTTP or HTTPS URL.")
    if not owner.strip():
        raise ValueError("An owner is required.")
    for _ in range(5):
        code = _new_code()
        try:
            store.save(database_path, code, destination, owner)
            return code
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Could not allocate a unique short code.")


def resolve(database_path: str, code: str) -> str | None:
    """Resolve a short code and record the visit."""
    if not code.isalnum():
        return None
    return store.find(database_path, code)


def list_links(database_path: str, owner: str) -> list[dict[str, object]]:
    """List the calling owner's URL mappings."""
    if not owner.strip():
        raise ValueError("An owner is required.")
    return store.list_by_owner(database_path, owner)


def link_stats(database_path: str, owner: str) -> dict[str, int]:
    """Return aggregate link counts for a validated owner."""
    if not owner.strip():
        raise ValueError("An owner is required.")
    return store.owner_stats(database_path, owner)


def delete_link(database_path: str, code: str, owner: str) -> bool:
    """Delete a code only for its owner."""
    if not owner.strip():
        raise ValueError("An owner is required.")
    return store.remove(database_path, code, owner)
