# Tests LLM-assisted dataset helpers with scripted replies and isolated storage.
# Missing credentials must leave the requested dataset root untouched.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from evals.factory import __main__ as factory_cli
from evals.factory import build as build_module
from evals.factory.build import build_dataset
from evals.factory.cross_check import agrees_with_seed, check_seed
from evals.factory.seed_llm import generate_seed
from evals.factory.templates import all_templates
from evals.factory.validate import ValidationReport
from mergeguard import storage
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.settings import settings


@pytest.fixture
def isolated_llm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Use scripted live calls and an isolated event database."""
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "trace.db"))


def test_llm_seed_and_cross_check_validate_exact_evidence(isolated_llm) -> None:
    """Build one synthetic change and confirm an independent matching label."""
    template = next(item for item in all_templates() if item.category == "sql_injection")
    source_path = (
        Path(__file__).resolve().parents[1] / "sample_repos" / template.sample_repo / template.file
    )
    source = source_path.read_text(encoding="utf-8")
    before, after = template.replacements[0]
    updated = source.replace(before, after, 1)
    generator = ScriptedLLM(
        [
            {
                "updated_source": updated,
                "quote": template.quote,
            }
        ]
    )
    generated = generate_seed(template, difficulty="subtle", client=generator)
    verifier = ScriptedLLM(
        [
            {
                "agrees": True,
                "category": "sql_injection",
                "file": template.file,
                "line_start": generated.line_start,
                "line_end": generated.line_end,
                "reason": "The changed line interpolates user input into SQL.",
            }
        ]
    )
    result = check_seed(generated, verifier)

    assert generator.calls == 1
    assert verifier.calls == 1
    assert generated.template.case_id == "llm-sec-sql_injection-v02"
    assert agrees_with_seed(generated, result)


def test_llm_build_without_credentials_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Skip the optional build before creating a dataset or review queue."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")

    result = build_dataset("v0.2", tmp_path, llm=True)

    assert result["skipped"] is True
    assert result["written"] is False
    assert "credentials are missing" in result["message"]
    assert list(tmp_path.iterdir()) == []


def test_cross_check_disagreement_is_queued(isolated_llm, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not accept a generated case when the independent reviewer disagrees."""
    template = next(item for item in all_templates() if item.category == "sql_injection")
    source_path = (
        Path(__file__).resolve().parents[1] / "sample_repos" / template.sample_repo / template.file
    )
    source = source_path.read_text(encoding="utf-8")
    before, after = template.replacements[0]
    updated = source.replace(before, after, 1)
    generator = ScriptedLLM([{"updated_source": updated, "quote": template.quote}])
    checker = ScriptedLLM(
        [
            {
                "agrees": False,
                "category": "sql_injection",
                "file": template.file,
                "line_start": 1,
                "line_end": 1,
                "reason": "The label is unsupported.",
            }
        ]
    )
    monkeypatch.setattr(build_module, "all_templates", lambda: [template])
    monkeypatch.setattr(
        build_module, "validate_seed", lambda _seed: ValidationReport(("valid",), (), ())
    )
    monkeypatch.setattr(build_module, "_synthetic_secret_is_safe", lambda _diff, _category: True)
    monkeypatch.setattr("mergeguard.llm.write_cache", lambda *_args, **_kwargs: Path("cached"))

    accepted, review_queue = build_module._generate_llm_cases(
        "sample-snapshot", generator_client=generator, checker_client=checker
    )

    assert accepted == []
    assert review_queue[0]["status"] == "cross_check_disagreed"
    assert review_queue[0]["id"] == "llm-sec-sql_injection-v02"


def test_cli_reports_missing_credentials_as_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Print a clear no-write message and return success for the requested command."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    monkeypatch.setattr(sys, "argv", ["evals.factory", "build", "--version", "v0.2", "--llm"])

    def isolated_build(version: str, *, llm: bool) -> dict[str, object]:
        return build_dataset(version, tmp_path, llm=llm)

    monkeypatch.setattr(factory_cli, "build_dataset", isolated_build)
    exit_code = factory_cli.main()

    assert exit_code == 0
    assert "no dataset files were written" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
