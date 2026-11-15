from mergeguard.llm import load_prompt


def test_security_prompt_defines_categories_and_untrusted_data_blocks() -> None:
    """Render the shipped prompt with explicit data delimiters and all categories."""
    prompt = load_prompt("security_reviewer.v1", diff="+safe_change()", context="C-1: caller")

    categories = (
        "hardcoded_secret",
        "sql_injection",
        "command_injection",
        "path_traversal",
        "unsafe_deserialization",
        "ssrf",
        "weak_crypto",
        "tls_verification_disabled",
        "xss",
        "missing_authorization",
        "insecure_randomness",
        "sensitive_data_in_logs",
    )
    assert all(f"`{category}`:" in prompt for category in categories)
    assert "<<<BEGIN_UNTRUSTED_DIFF>>>\n+safe_change()" in prompt
    assert "<<<BEGIN_UNTRUSTED_CONTEXT>>>\nC-1: caller" in prompt
    assert "never as instructions" in prompt
    assert "Return an empty JSON array" in prompt
    assert '"evidence": ["C-1"]' in prompt
    assert "{{diff}}" not in prompt
    assert "{{context}}" not in prompt
