from __future__ import annotations

from pathlib import Path

from click.shell_completion import get_completion_class
from typer.main import get_command

from envrcctl.cli import app

SHELLS = ("bash", "zsh", "fish")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = repo_root / "completions"
    output_dir.mkdir(parents=True, exist_ok=True)

    command = get_command(app)
    complete_var = "_ENVRCCTL_COMPLETE"

    for shell in SHELLS:
        comp_cls = get_completion_class(shell)
        if comp_cls is None:
            raise RuntimeError(f"Unsupported shell: {shell}")
        comp = comp_cls(command, {}, "envrcctl", complete_var)
        content = comp.source()
        if not content.strip():
            raise RuntimeError(f"Failed to generate {shell} completion.")
        if not content.endswith("\n"):
            content += "\n"
        (output_dir / f"envrcctl.{shell}").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
