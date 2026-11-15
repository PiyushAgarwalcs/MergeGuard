# Shared options passed from the evaluation CLI into suite functions.
# The contract stays separate so suite registration does not create import cycles.

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalConfig:
    """Shared input settings passed to a suite runner."""

    layer: str
    split: str | None = None
    repeats: int = 1
    cases: int | None = None
    mode: str = "replay"
    dataset_version: str = "v0.1"
