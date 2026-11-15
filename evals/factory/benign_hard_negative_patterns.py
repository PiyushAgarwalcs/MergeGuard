# Risky-looking but safe-by-construction code patterns.
# Destinations and credentials are synthetic fixtures only.

HARD_NEGATIVE_PATTERNS = (
    (
        "sql_injection",
        "notes_api",
        "notes_tests/test_notes.py",
        "def safe_query_01(connection, note_id):\n    return connection.execute('SELECT id FROM notes WHERE id = ?', (note_id,))",
    ),
    (
        "sql_injection",
        "notes_api",
        "notes_tests/test_notes.py",
        "def safe_query_02(connection, owner):\n    return connection.execute('SELECT id FROM notes WHERE user_id = ?', (owner,))",
    ),
    (
        "sql_injection",
        "notes_api",
        "notes_tests/test_notes.py",
        "def safe_query_03(connection, note_id, owner):\n    return connection.execute('SELECT id FROM notes WHERE id = ? AND user_id = ?', (note_id, owner))",
    ),
    (
        "hardcoded_secret",
        "notes_api",
        "notes_tests/test_notes.py",
        'def safe_fixture_token():\n    return "test-token-only"',
    ),
    (
        "hardcoded_secret",
        "notes_api",
        "notes_tests/test_notes.py",
        'def safe_env_token():\n    import os\n    return os.environ.get("TEST_API_TOKEN", "")',
    ),
    (
        "hardcoded_secret",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def safe_fixture_key():\n    return "fixture-key-not-a-secret"',
    ),
    (
        "command_injection",
        "csv_report",
        "report_tests/test_report.py",
        'def safe_command():\n    import subprocess\n    return subprocess.run(["renderer", "--version"], shell=False, check=True)',
    ),
    (
        "command_injection",
        "csv_report",
        "report_tests/test_report.py",
        'def safe_fixed_command():\n    import subprocess\n    return subprocess.run(["python", "--version"], shell=False, check=True)',
    ),
    (
        "path_traversal",
        "csv_report",
        "report_tests/test_report.py",
        'def safe_fixed_report(root):\n    from pathlib import Path\n    return (Path(root).resolve() / "summary.csv").resolve()',
    ),
    (
        "path_traversal",
        "csv_report",
        "report_tests/test_report.py",
        'def safe_validated_path(root, name):\n    from report_tool.paths import contained_path\n    return contained_path(root, name, ".csv")',
    ),
    (
        "tls_verification_disabled",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "def safe_tls_request(url):\n    import httpx\n    return httpx.get(url, verify=True, timeout=5.0)",
    ),
    (
        "tls_verification_disabled",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "def safe_tls_options(url):\n    import httpx\n    return httpx.get(url, timeout=2.0, verify=True)",
    ),
    (
        "ssrf",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "def safe_allowlisted_host(url, hosts):\n    from urllib.parse import urlparse\n    return urlparse(url).hostname in hosts",
    ),
    (
        "ssrf",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "def safe_scheme_check(url):\n    from shortener.config import is_http_url\n    return is_http_url(url)",
    ),
    (
        "unsafe_deserialization",
        "notes_api",
        "notes_tests/test_notes.py",
        "def safe_json_input(text):\n    import json\n    return json.loads(text)",
    ),
    (
        "xss",
        "csv_report",
        "report_tests/test_report.py",
        "def safe_html_label(label):\n    from html import escape\n    return escape(label, quote=True)",
    ),
    (
        "insecure_randomness",
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "def safe_random_code():\n    import secrets\n    return secrets.token_urlsafe(16)",
    ),
    (
        "missing_authorization",
        "notes_api",
        "notes_tests/test_notes.py",
        "def safe_token_compare(provided, expected):\n    import hmac\n    return hmac.compare_digest(provided, expected)",
    ),
    (
        "sensitive_data_in_logs",
        "notes_api",
        "notes_tests/test_notes.py",
        'def safe_credential_log(logger, fingerprint):\n    logger.info("Authentication failed for token fingerprint %s", fingerprint)',
    ),
    (
        "command_injection",
        "csv_report",
        "report_tests/test_report.py",
        "def safe_shell_free_command(program, report):\n    import subprocess\n    return subprocess.run([program, str(report)], shell=False, check=True)",
    ),
)
