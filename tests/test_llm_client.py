# Tests the LLM client with scripted replies and isolated cache/database paths.
# No test sends an HTTP request or needs model credentials.

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from mergeguard import storage
from mergeguard.llm import (
    LLMDisabled,
    MissingCredentials,
    ReplayMiss,
    ask_for_list,
    ask_for_object,
    load_prompt,
)
from mergeguard.llm_cache import cache_key
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.llm_json import InvalidModelOutput, parse_json_reply
from mergeguard.models import Finding
from mergeguard.settings import settings
from mergeguard.storage import get_events


class SampleObject(BaseModel):
    """Small schema used to prove output validation."""

    value: int


@pytest.fixture
def isolated_trace_db(tmp_path, monkeypatch):
    """Redirect trace writes to a disposable SQLite file."""
    database = tmp_path / "trace.db"
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))
    yield database


def test_load_prompt_reads_version_and_substitutes_values(tmp_path, monkeypatch):
    """Load one versioned prompt without altering other brace expressions."""
    monkeypatch.setattr("mergeguard.llm.PROMPTS_DIR", tmp_path)
    prompt_file = tmp_path / "sample.v1.md"
    prompt_file.write_text("Review {diff}. Output JSON object {{schema}}.", encoding="utf-8")
    prompt = load_prompt("sample.v1", diff="change", schema="object")
    assert prompt == "Review change. Output JSON object object."


def test_parse_json_reply_accepts_fences_and_prose_prefix():
    """Parse fenced JSON and a short introduction before the JSON value."""
    assert parse_json_reply('```json\n[{"value": 4}]\n```') == [{"value": 4}]
    assert parse_json_reply('Result:\n{"value": 5}') == {"value": 5}


def test_parse_json_reply_rejects_text_without_json():
    """Return a clear validation error when a reply has no JSON value."""
    with pytest.raises(InvalidModelOutput):
        parse_json_reply("No findings.")


def test_ask_for_list_validates_fenced_model_output(monkeypatch, tmp_path, isolated_trace_db):
    """Return Pydantic items and trace one scripted call."""
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    client = ScriptedLLM(['```json\n[{"value": 7}]\n```'])
    result = ask_for_list(
        "Find values",
        SampleObject,
        "security_reviewer",
        client=client,
        run_id="llm-list",
        cache_dir=tmp_path / "cache",
    )
    assert result == [SampleObject(value=7)]
    assert client.calls == 1
    assert len(get_events("llm-list")) == 1


def test_ask_for_object_validates_one_pydantic_instance(monkeypatch, tmp_path, isolated_trace_db):
    """Return one validated object from scripted JSON."""
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    client = ScriptedLLM([{"value": 8}])
    result = ask_for_object(
        "Return a value",
        SampleObject,
        "security_reviewer",
        client=client,
        run_id="llm-object",
        cache_dir=tmp_path / "cache",
    )
    assert result.value == 8


def test_record_mode_retries_validation_and_replay_uses_both_cache_entries(
    monkeypatch, tmp_path, isolated_trace_db
):
    """Cache the invalid first answer and repaired retry for later replay."""
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(settings, "LLM_MODE", "record")
    client = ScriptedLLM([{"value": "bad"}, {"value": 9}])
    result = ask_for_object(
        "Return an integer",
        SampleObject,
        "security_reviewer",
        client=client,
        run_id="llm-record",
        cache_dir=cache_dir,
    )
    assert result.value == 9
    assert client.calls == 2
    assert len(list(cache_dir.glob("*.json"))) == 2

    monkeypatch.setattr(settings, "LLM_MODE", "replay")
    unused = ScriptedLLM([])
    replayed = ask_for_object(
        "Return an integer",
        SampleObject,
        "security_reviewer",
        client=unused,
        run_id="llm-replay",
        cache_dir=cache_dir,
    )
    assert replayed == result
    assert unused.calls == 0


def test_second_invalid_response_raises_after_exactly_one_retry(
    monkeypatch, tmp_path, isolated_trace_db
):
    """Stop after the second malformed model response."""
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    client = ScriptedLLM(["not json", "still not json"])
    with pytest.raises(InvalidModelOutput):
        ask_for_object(
            "Return an object",
            SampleObject,
            "security_reviewer",
            client=client,
            cache_dir=tmp_path / "cache",
        )
    assert client.calls == 2


def test_replay_mode_raises_cache_miss(monkeypatch, tmp_path, isolated_trace_db):
    """Never contact the API when replay data is missing."""
    monkeypatch.setattr(settings, "LLM_MODE", "replay")
    client = ScriptedLLM([{"value": 1}])
    with pytest.raises(ReplayMiss):
        ask_for_object(
            "missing prompt",
            SampleObject,
            "security_reviewer",
            client=client,
            cache_dir=tmp_path / "cache",
        )
    assert client.calls == 0


def test_off_mode_blocks_even_a_scripted_client(monkeypatch, tmp_path):
    """Respect the explicit off mode before touching any transport."""
    monkeypatch.setattr(settings, "LLM_MODE", "off")
    with pytest.raises(LLMDisabled):
        ask_for_object(
            "prompt",
            SampleObject,
            "security_reviewer",
            client=ScriptedLLM([]),
            cache_dir=tmp_path,
        )


def test_live_mode_without_credentials_fails_clearly(monkeypatch, tmp_path, isolated_trace_db):
    """Avoid importing or calling the provider without configured credentials."""
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    with pytest.raises(MissingCredentials):
        ask_for_object("prompt", SampleObject, "security_reviewer", cache_dir=tmp_path)


def test_ollama_mode_uses_flattened_structured_schema_without_api_key(
    monkeypatch, tmp_path, isolated_trace_db
):
    """Send Ollama a wrapped list schema, flatten Pydantic refs, and validate its reply."""
    import openai

    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_MODE", "live")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    returned_finding = {
        "id": "F-1",
        "source": "security_reviewer",
        "category": "command_injection",
        "severity": "high",
        "file": "app.py",
        "line_start": 2,
        "line_end": 2,
        "quote": "subprocess.run(cmd, shell=True)",
        "explanation": "The shell interprets untrusted input.",
        "suggestion": "Pass arguments as a list and disable the shell.",
        "evidence": [],
    }
    capture = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            capture["client"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            capture["request"] = kwargs
            content = json.dumps({"items": [returned_finding]})
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=12),
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    result = ask_for_list(
        "Return one finding.",
        Finding,
        "security_reviewer",
        run_id="ollama-schema",
        cache_dir=tmp_path / "cache",
    )

    assert result == [Finding.model_validate(returned_finding)]
    assert capture["client"]["api_key"] == "ollama"
    assert capture["client"]["base_url"] == "http://localhost:11434/v1"
    response_schema = capture["request"]["response_format"]["json_schema"]["schema"]
    assert "$defs" not in json.dumps(response_schema)
    assert response_schema["properties"]["items"]["items"]["properties"]["source"]["enum"]


def test_cache_key_changes_with_model_prompt_and_parameters():
    """Separate cached requests when any request-defining input changes."""
    key = cache_key("model-a", "prompt", {"temperature": 0})
    assert key != cache_key("model-b", "prompt", {"temperature": 0})
    assert key != cache_key("model-a", "other", {"temperature": 0})
    assert key != cache_key("model-a", "prompt", {"temperature": 1})
