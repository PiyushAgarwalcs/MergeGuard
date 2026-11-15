# Security seed patterns for paths, data parsing and network destinations.
# Replacements remain syntactically valid Python for mechanical validation.

from evals.factory.template_types import CategoryPattern


def patterns() -> list[CategoryPattern]:
    """Return path traversal, deserialization, SSRF, and crypto patterns."""
    path_before = """    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Expected a simple file name.")
    root = directory.resolve()
    candidate = (root / f"{name}{suffix}").resolve()
    if candidate.parent != root:
        raise ValueError("File path escapes the configured directory.")"""
    path_outputs = tuple(
        f"""    if not name:
        raise ValueError("Expected a simple file name.")
    root = directory.resolve()
    candidate = (root / f"{{name}}{{suffix}}").resolve()
    if candidate.parent != root and {condition}:
        raise ValueError("File path escapes the configured directory.")"""
        for condition in (
            "not name.startswith('..')",
            "'..' not in name",
            "not name.startswith('../')",
            "name.count('..') == 0",
        )
    )
    path_quotes = (
        "    if candidate.parent != root and not name.startswith('..'):",
        "    if candidate.parent != root and '..' not in name:",
        "    if candidate.parent != root and not name.startswith('../'):",
        "    if candidate.parent != root and name.count('..') == 0:",
    )
    return [
        CategoryPattern(
            "path_traversal",
            "csv_report",
            "report_tool/paths.py",
            "high",
            path_before,
            path_outputs,
            path_quotes,
            "Untrusted file names can bypass containment checks and escape the data directory.",
            "Reject path components and verify the resolved path remains beneath the root.",
        ),
        CategoryPattern(
            "unsafe_deserialization",
            "notes_api",
            "notes_api/imports.py",
            "critical",
            "    decoded = json.loads(payload)",
            (
                "    decoded = pickle.loads(payload)",
                "    decoded = pickle.loads(bytes(payload, encoding='utf-8'))",
                "    decoded = pickle.loads(payload.encode())",
                "    decoded = pickle.loads(payload[:])",
            ),
            (
                "    decoded = pickle.loads(payload)",
                "    decoded = pickle.loads(bytes(payload, encoding='utf-8'))",
                "    decoded = pickle.loads(payload.encode())",
                "    decoded = pickle.loads(payload[:])",
            ),
            "Untrusted import data is decoded with Python's executable pickle format.",
            "Use a data-only format such as JSON for untrusted input.",
            (("import json", "import pickle"),),
        ),
        CategoryPattern(
            "ssrf",
            "url_shortener",
            "shortener/preview.py",
            "high",
            "    if parsed.hostname.lower() not in allowed_hosts:",
            (
                "    if parsed.hostname is None:",
                "    if False:",
                "    if not allowed_hosts:",
                "    if parsed.hostname.lower() in allowed_hosts and False:",
            ),
            (
                "    if parsed.hostname is None:",
                "    if False:",
                "    if not allowed_hosts:",
                "    if parsed.hostname.lower() in allowed_hosts and False:",
            ),
            "A URL preview can reach a host outside the configured destination allowlist.",
            "Require an explicitly approved host before making outbound requests.",
        ),
        CategoryPattern(
            "weak_crypto",
            "notes_api",
            "notes_api/auth.py",
            "high",
            "    return hashlib.sha256(token.encode()).hexdigest()",
            (
                "    return hashlib.md5(token.encode()).hexdigest()",
                "    return hashlib.sha1(token.encode()).hexdigest()",
                "    return hashlib.md5(token.encode()).hexdigest()[:12]",
                "    return hashlib.sha1(token.encode()).hexdigest()[:12]",
            ),
            (
                "    return hashlib.md5(token.encode()).hexdigest()",
                "    return hashlib.sha1(token.encode()).hexdigest()",
                "    return hashlib.md5(token.encode()).hexdigest()[:12]",
                "    return hashlib.sha1(token.encode()).hexdigest()[:12]",
            ),
            "A weak hash is used for a credential-derived identifier.",
            "Use a modern cryptographic hash, or a keyed construction when appropriate.",
        ),
    ]
