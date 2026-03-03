from __future__ import annotations

from pathlib import Path

from envrctl import cli
from envrctl.envrc import ENVRC_FILENAME


def test_find_nearest_envrc_dir_returns_none(tmp_path: Path) -> None:
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)

    found = cli._find_nearest_envrc_dir(start)
    assert found is None


def test_find_nearest_envrc_dir_finds_parent(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)

    (parent / ENVRC_FILENAME).write_text("# placeholder", encoding="utf-8")

    found = cli._find_nearest_envrc_dir(child)
    assert found == parent
