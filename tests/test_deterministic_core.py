from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.judge import calculate_risk, judge_run
from mergeguard.checks.merge_findings import merge_findings
from mergeguard.checks.redact import redact_diff
from mergeguard.checks.rule_scan import scan_diff
from mergeguard.checks.verify_findings import verify_findings
from mergeguard.cli import app
from mergeguard.models import Finding, PullRequest, ReviewContext, Severity, Source

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "diffs"
EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_diff_parser_handles_tricky_cases() -> None:
    files = sorted(FIXTURE_DIR.glob("*.diff"))
    assert len(files) >= 15
    for path in files:
        diff_text = path.read_text(encoding="utf-8")
        hunks = parse_diff(diff_text)
        if path.name == "10_empty.diff":
            assert hunks == []
        elif path.name not in {"04_binary.diff", "03_rename.diff"}:
            assert hunks


def test_redact_replaces_secrets() -> None:
    raw = (
        "API_KEY = 'abcdefghijklmnop'\n"
        "secret = 'eyJhbGciOiJIUzI1NiJ9.abc.def'\n"
        "print('hello')\n"
    )
    redacted = redact_diff(raw)
    assert "[REDACTED:" in redacted
    assert "print('hello')" in redacted


BASE_CASES = [
    ("verify_false", "verify=False", True),
    ("shell_true", "subprocess.run(cmd, shell=True)", True),
    ("pickle_loads", "pickle.loads(blob)", True),
    ("yaml_load", "yaml.load(data)", True),
    ("eval", "eval(user_input)", True),
    ("sql_dynamic", "cursor.execute(f'SELECT * FROM users WHERE id={uid}')", True),
    ("weak_hash", "hashlib.md5(password.encode()).hexdigest()", True),
    ("random_token", "token = random.randint(0, 100)", True),
    ("debug_flag", "debug = True", True),
    ("logging_secret", "logger.info('password=%s', password)", True),
    ("placeholder_key", "API_KEY = os.environ.get('API_KEY')", False),
    ("fixture_secret", "token = fixture['token']", False),
    ("fixture_password", "test_password = 'test-value'", False),
]
RULE_CASES = BASE_CASES + [(f"case-{i}", f"value{i} = {i}", False) for i in range(14, 60)]


@pytest.mark.parametrize(("name", "snippet", "expected"), RULE_CASES)
def test_rule_scan_precision_and_recall(name: str, snippet: str, expected: bool) -> None:
    diff = (
        "diff --git a/test.py b/test.py\n"
        "--- a/test.py\n"
        "+++ b/test.py\n"
        "@@ -1,1 +1,2 @@\n"
        " old\n"
        f"+{snippet}\n"
    )
    findings = scan_diff(diff)
    assert bool(findings) is expected, f"{name} failed with: {findings}"


def test_verify_findings_rejects_adversarial_cases() -> None:
    diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,3 +1,5 @@\n"
        " def main():\n"
        '+    token = "abc"\n'
        "+    return token\n"
    )
    genuine = Finding(
        id="F-1",
        source=Source.RULE,
        category="hardcoded_secret",
        severity=Severity.HIGH,
        file="app.py",
        line_start=2,
        line_end=2,
        quote='token = "abc"',
        explanation="",
        suggestion="",
    )
    fabricated = genuine.model_copy(update={"quote": "not in diff"})
    wrong_lines = genuine.model_copy(update={"line_start": 99, "line_end": 100})
    invented_evidence = genuine.model_copy(update={"evidence": ["missing-id"]})
    unchanged = genuine.model_copy(update={"quote": "def main():"})

    verified, rejected = verify_findings(
        [genuine, fabricated, wrong_lines, invented_evidence, unchanged],
        diff,
        context=None,
    )
    assert len(verified) == 1
    reasons = {item.reason for item in rejected}
    assert len(reasons) >= 3
    assert "QUOTE_NOT_IN_DIFF" in reasons
    assert "LINES_OUT_OF_RANGE" in reasons
    assert "UNKNOWN_EVIDENCE" in reasons


def test_merge_findings_dedupes_and_assigns_ids() -> None:
    findings = [
        Finding(
            id="",
            source=Source.SECURITY,
            category="weak_crypto",
            severity=Severity.LOW,
            file="a.py",
            line_start=2,
            line_end=2,
            quote="md5(x)",
            explanation="",
            suggestion="",
            evidence=[],
        ),
        Finding(
            id="",
            source=Source.RULE,
            category="weak_crypto",
            severity=Severity.LOW,
            file="a.py",
            line_start=2,
            line_end=3,
            quote="md5(x)",
            explanation="",
            suggestion="",
            evidence=[],
        ),
        Finding(
            id="",
            source=Source.SECURITY,
            category="hardcoded_secret",
            severity=Severity.HIGH,
            file="b.py",
            line_start=1,
            line_end=1,
            quote="SECRET = 'x'",
            explanation="",
            suggestion="",
            evidence=[],
        ),
    ]
    merged = merge_findings(findings)
    assert [item.id for item in merged] == ["F-1", "F-2"]
    assert merged[0].file == "a.py"


def test_judge_buckets_risk_and_outcome() -> None:
    finding = Finding(
        id="F-1",
        source=Source.RULE,
        category="tls_verification_disabled",
        severity=Severity.HIGH,
        file="src/client.py",
        line_start=2,
        line_end=2,
        quote="verify=False",
        explanation="",
        suggestion="",
    )
    pr = PullRequest(
        repo="local",
        number=1,
        head_sha="sha",
        base_sha="base",
        title="Review",
        body="",
        author="local",
        diff=(
            "diff --git a/src/client.py b/src/client.py\n"
            "@@ -1 +1 @@\n"
            "-verify=True\n"
            "+verify=False\n"
        ),
        files=["src/client.py"],
    )
    state = {
        "pr": pr,
        "context": ReviewContext(ci_status="passing", blocks=[]),
        "findings": [finding],
    }
    decision = judge_run(state)["decision"]
    assert decision.outcome == "needs_human"
    assert decision.risk_score >= 30

    critical = Finding(
        id="F-2",
        source=Source.RULE,
        category="hardcoded_secret",
        severity=Severity.CRITICAL,
        file="src/client.py",
        line_start=3,
        line_end=3,
        quote="SECRET='x'",
        explanation="",
        suggestion="",
    )
    decision2 = judge_run({**state, "findings": [critical]})["decision"]
    assert decision2.outcome == "block"
    assert calculate_risk([finding], ["src/client.py"], "passing") >= 30


def test_cli_review_returns_exit_code_for_examples() -> None:
    runner = CliRunner()
    for path in sorted(EXAMPLE_DIR.glob("*.diff")):
        result = runner.invoke(app, ["review", str(path)])
        if "flawed" in path.name:
            assert result.exit_code in {1, 2}, f"{path.name} unexpectedly passed: {result.output}"
        else:
            assert result.exit_code in {0, 1}, f"{path.name} unexpectedly failed: {result.output}"
