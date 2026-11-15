# JSON import helpers for the sample notes service.
# Untrusted import text is parsed as data, not executable object state.

import json


def load_import_payload(payload: bytes | str) -> dict[str, object]:
    """Decode a JSON object used by the notes import endpoint."""
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise TypeError("An imported note payload must be a JSON object.")
    return decoded
