# tests/test_settings.py
# Verifies settings load with defaults when the environment is empty.

from pathlib import Path

from dotenv import dotenv_values

from mergeguard.settings import Settings, load_settings


def test_settings_loads_defaults() -> None:
    loaded = load_settings()
    assert isinstance(loaded, Settings)
    assert loaded.LLM_MODE == "replay"
    assert loaded.RISK_THRESHOLD == 71


def test_env_example_lists_every_settings_field() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env.example"
    values = dotenv_values(env_file)
    assert set(values) == set(Settings.model_fields)
    defaults = Settings().model_dump()
    for name, default in defaults.items():
        value = values[name]
        if isinstance(default, bool):
            assert str(value).lower() == str(default).lower()
        else:
            assert (value or "") == str(default or "")
