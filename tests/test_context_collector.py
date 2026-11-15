from __future__ import annotations

from pathlib import Path

import pytest

from mergeguard.checks.collect_context import collect_context


def _snapshot(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "tests").mkdir()
    (root / "pkg" / "service.py").write_text(
        "def changed(value):\n    return value\n\ndef sibling():\n    return 1\n",
        encoding="utf-8",
    )
    (root / "pkg" / "consumer.py").write_text(
        "from pkg.service import changed\n\ndef caller(value):\n    return changed(value)\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_service.py").write_text(
        "from pkg.service import changed\ndef test_changed():\n    changed('x')\n",
        encoding="utf-8",
    )


def test_collects_related_context_and_missing_ci(tmp_path: Path) -> None:
    _snapshot(tmp_path)
    context = collect_context(
        tmp_path,
        ["pkg/service.py", "tests/test_service.py"],
        "+def changed(value):\n",
    )
    kinds = [block.kind for block in context.blocks]
    assert context.ci_status == "missing"
    assert context.changed_source_files == ["pkg/service.py"]
    assert context.changed_test_files == ["tests/test_service.py"]
    assert {"caller", "test", "sibling"} <= set(kinds)
    assert all(len(block.text) <= 1600 for block in context.blocks)


def test_context_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _snapshot(tmp_path)
    monkeypatch.setattr("mergeguard.checks.collect_context.MAX_CONTEXT_BLOCKS", 2)
    context = collect_context(tmp_path, ["pkg/service.py"], "+def changed(value):\n", "passing")
    assert len(context.blocks) == 2


@pytest.mark.parametrize("path", ["../outside.py", "/outside.py", "C:/outside.py"])
def test_rejects_non_repository_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError, match="relative to the repository"):
        collect_context(tmp_path, [path])
