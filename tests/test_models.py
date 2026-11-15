# tests/test_models.py
# Ensures the project contracts validate expected inputs and reject bad data.

import pytest
from pydantic import ValidationError

from mergeguard.models import Finding, Severity, Source


def test_finding_validates() -> None:
    finding = Finding(
        id="F-1",
        source=Source.RULE,
        category="hardcoded_secret",
        severity=Severity.CRITICAL,
        file="src/example.py",
        line_start=10,
        line_end=12,
        quote="TOKEN=abc",
        explanation="Hardcoded secret in config.",
        suggestion="Use environment variables.",
    )
    assert finding.file == "src/example.py"


def test_finding_rejects_bad_category() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id="F-2",
            source=Source.SECURITY,
            category="not_a_real_category",
            severity=Severity.HIGH,
            file="src/example.py",
            line_start=1,
            line_end=2,
            quote="print(123)",
            explanation="Bad category.",
            suggestion="Use a valid category.",
        )
