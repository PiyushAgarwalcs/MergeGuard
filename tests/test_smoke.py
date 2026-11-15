# tests/test_smoke.py
# Confirms the package imports cleanly in a fresh environment.

import mergeguard


def test_imports() -> None:
    assert mergeguard.__version__
