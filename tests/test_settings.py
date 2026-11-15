# tests/test_settings.py
# Verifies settings load with defaults when the environment is empty.

from mergeguard.settings import Settings, load_settings


def test_settings_loads_defaults() -> None:
    loaded = load_settings()
    assert isinstance(loaded, Settings)
    assert loaded.LLM_MODE == "replay"
    assert loaded.RISK_THRESHOLD == 71
