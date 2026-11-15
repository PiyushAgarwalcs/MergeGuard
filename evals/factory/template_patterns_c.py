# Security seed patterns for transport, output, identity and logging.
# Each finding quote points to a line inserted by its template.

from evals.factory.template_types import CategoryPattern


def patterns() -> list[CategoryPattern]:
    """Return TLS, XSS, authorization, randomness, and logging patterns."""
    tls_outputs = (
        "    response = httpx.get(destination, timeout=2.5, verify=False)",
        "    response = httpx.get(destination, verify=False)",
        "    response = httpx.get(destination, timeout=5.0, verify=False)",
        "    response = httpx.get(destination, verify=False, timeout=5.0)",
    )
    xss_outputs = (
        "        safe_category = category",
        '        safe_category = category.replace("<", "<")',
        '        safe_category = category.replace(">", ">")',
        """        safe_category = category.replace('"', '"')""",
    )
    authorization_outputs = (
        "        if not token:",
        "        if token is None:",
        "        if not token.strip():",
        "        if len(token) < 0:",
    )
    random_outputs = (
        '    return "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))',
        '    return "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))',
        '    return "".join(random.sample(CODE_ALPHABET, CODE_LENGTH))',
        '    return "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH - 1))',
    )
    log_outputs = (
        '            LOGGER.warning("Rejected API token %s.", token)',
        '            LOGGER.warning("Rejected notes credential: %s", token)',
        '            LOGGER.warning("Invalid credential %s was supplied.", token)',
        '            LOGGER.warning("Authentication failed for token=%s", token)',
    )
    return [
        CategoryPattern(
            "tls_verification_disabled",
            "url_shortener",
            "shortener/preview.py",
            "high",
            "    response = httpx.get(destination, timeout=5.0, verify=True)",
            tls_outputs,
            tls_outputs,
            "TLS certificate verification is disabled for an outbound request.",
            "Leave TLS verification enabled and configure trusted certificates explicitly.",
        ),
        CategoryPattern(
            "xss",
            "csv_report",
            "report_tool/html_report.py",
            "high",
            "        safe_category = escape(category, quote=True)",
            xss_outputs,
            xss_outputs,
            "Untrusted category markup is inserted into HTML without escaping.",
            "HTML-escape untrusted text before placing it in the document.",
        ),
        CategoryPattern(
            "missing_authorization",
            "url_shortener",
            "shortener/api.py",
            "high",
            "        if not self.api_token or not hmac.compare_digest(token, self.api_token):",
            authorization_outputs,
            authorization_outputs,
            "An owner-scoped operation no longer compares credentials with the configured token.",
            "Compare the supplied credential against the configured token on every request.",
        ),
        CategoryPattern(
            "insecure_randomness",
            "url_shortener",
            "shortener/service.py",
            "high",
            '    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))',
            random_outputs,
            random_outputs,
            "Short URL codes are generated with a predictable pseudo-random generator.",
            "Use a cryptographically secure random source for bearer-like codes.",
            (("import secrets", "import random"),),
        ),
        CategoryPattern(
            "sensitive_data_in_logs",
            "notes_api",
            "notes_api/api.py",
            "high",
            '            LOGGER.warning("Rejected notes API request with invalid credentials.")',
            log_outputs,
            log_outputs,
            "A raw credential is included in an authentication failure log.",
            "Log a stable non-reversible fingerprint or omit credential values.",
        ),
    ]
