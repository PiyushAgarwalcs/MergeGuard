# mergeguard.settings
# Loads configuration from environment and .env files while keeping imports safe when secrets are missing.

from __future__ import annotations

import os
from typing import Literal

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

DATABASE_PATH = "data/mergeguard.db"
RISK_THRESHOLD = 71
MAX_DIFF_LINES = 2000
AGENT_TIMEOUT_SECONDS = 60
RISK_HIGH_FINDING_WEIGHT = 30
RISK_MEDIUM_FINDING_WEIGHT = 10
RISK_LOW_FINDING_WEIGHT = 2
RISK_CHANGED_LINES_400 = 10
RISK_CHANGED_LINES_1000 = 20
RISK_STRICTER_PATHS = 15
RISK_SOURCE_WITHOUT_TEST = 10
RISK_CI_FAILING = 25
RISK_DEPENDENCY_FILE = 5


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    LLM_PROVIDER: Literal["openai_compatible", "ollama"] = "openai_compatible"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    REVIEWER_MODEL: str = "gpt-4o-mini"
    SKEPTIC_MODEL: str = "gpt-4o-mini"
    CROSS_CHECK_MODEL: str = ""
    JUDGE_MODEL: str = "gpt-4o-mini"
    GENERATOR_MODEL: str = "gpt-4o-mini"
    LLM_MODE: Literal["live", "record", "replay", "off"] = "replay"
    DATABASE_PATH: str = "data/mergeguard.db"
    PRIVACY_MODE: bool = False
    MERGEGUARD_GITHUB_TOKEN: str = ""
    TEST_REPO: str = ""
    MERGEGUARD_WEBHOOK_SECRET: str = ""
    RISK_THRESHOLD: int = Field(default=RISK_THRESHOLD, ge=0, le=100)
    MAX_DIFF_LINES: int = Field(default=MAX_DIFF_LINES, ge=1)
    AGENT_TIMEOUT_SECONDS: int = Field(default=AGENT_TIMEOUT_SECONDS, ge=1)


def load_settings() -> Settings:
    env_values = dotenv_values()
    raw_env = {**(env_values or {}), **os.environ}
    normalized: dict[str, object] = {}
    for key, value in raw_env.items():
        if value in (None, ""):
            continue
        if key == "PRIVACY_MODE":
            normalized[key] = str(value).lower() in {"1", "true", "yes", "on"}
        elif key in {"RISK_THRESHOLD", "MAX_DIFF_LINES", "AGENT_TIMEOUT_SECONDS"}:
            normalized[key] = int(value)
        else:
            normalized[key] = value
    return Settings.model_validate(normalized)


settings = load_settings()

__all__ = [
    "AGENT_TIMEOUT_SECONDS",
    "DATABASE_PATH",
    "MAX_DIFF_LINES",
    "RISK_CI_FAILING",
    "RISK_DEPENDENCY_FILE",
    "RISK_HIGH_FINDING_WEIGHT",
    "RISK_LOW_FINDING_WEIGHT",
    "RISK_MEDIUM_FINDING_WEIGHT",
    "RISK_SOURCE_WITHOUT_TEST",
    "RISK_STRICTER_PATHS",
    "RISK_THRESHOLD",
    "Settings",
    "load_settings",
    "settings",
]
