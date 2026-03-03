import runpy
import sys

import envrcctl.cli as cli
import envrcctl.main as main


def test_main_invokes_app(monkeypatch) -> None:
    called = {"ok": False}

    def fake_app() -> None:
        called["ok"] = True

    monkeypatch.setattr(main, "app", fake_app)
    main.main()

    assert called["ok"] is True


def test_main_module_runs_as_script(monkeypatch) -> None:
    called = {"ok": False}

    def fake_app() -> None:
        called["ok"] = True

    monkeypatch.setattr(cli, "app", fake_app)
    sys.modules.pop("envrcctl.main", None)
    runpy.run_module("envrcctl.main", run_name="__main__")

    assert called["ok"] is True
