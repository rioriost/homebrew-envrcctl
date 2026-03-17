from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from envrcctl import auth
from envrcctl.errors import EnvrcctlError


class DummyCompletedProcess:
    def __init__(self, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr


def test_default_helper_path_points_next_to_module() -> None:
    path = auth._default_helper_path()

    assert path.name == "envrcctl-macos-auth"
    assert path.parent == Path(auth.__file__).resolve().parent


def test_helper_path_uses_env_var(monkeypatch, tmp_path: Path) -> None:
    helper_path = tmp_path / "custom-helper"
    monkeypatch.setenv("ENVRCCTL_MACOS_AUTH_HELPER", str(helper_path))

    path = auth._helper_path()

    assert path == helper_path


def test_helper_path_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("ENVRCCTL_MACOS_AUTH_HELPER", raising=False)

    path = auth._helper_path()

    assert path == auth._default_helper_path()


def test_ensure_helper_ready_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing-helper"

    with pytest.raises(EnvrcctlError) as exc:
        auth._ensure_helper_ready(missing)

    assert "not found" in str(exc.value).lower()


def test_ensure_helper_ready_requires_regular_file(tmp_path: Path) -> None:
    helper_dir = tmp_path / "helper-dir"
    helper_dir.mkdir()

    with pytest.raises(EnvrcctlError) as exc:
        auth._ensure_helper_ready(helper_dir)

    assert "invalid" in str(exc.value).lower()


def test_ensure_helper_ready_requires_executable_file(tmp_path: Path) -> None:
    helper_path = tmp_path / "helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o644)

    with pytest.raises(EnvrcctlError) as exc:
        auth._ensure_helper_ready(helper_path)

    assert "not executable" in str(exc.value).lower()


def test_ensure_device_owner_auth_is_noop_off_macos(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return DummyCompletedProcess()

    monkeypatch.setattr(auth.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", fake_run)

    auth.ensure_device_owner_auth("Authenticate for envrcctl")

    assert calls == []


def test_ensure_device_owner_auth_rejects_empty_reason_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(auth.sys, "platform", "darwin")

    with pytest.raises(EnvrcctlError) as exc:
        auth.ensure_device_owner_auth("   ")

    assert "reason cannot be empty" in str(exc.value).lower()


def test_ensure_device_owner_auth_runs_helper(monkeypatch, tmp_path: Path) -> None:
    calls = []
    helper_path = tmp_path / "envrcctl-macos-auth"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyCompletedProcess()

    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setenv("ENVRCCTL_MACOS_AUTH_HELPER", str(helper_path))
    monkeypatch.setattr(subprocess, "run", fake_run)

    auth.ensure_device_owner_auth("Authenticate for envrcctl")

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == [
        str(helper_path),
        "--authorize-only",
        "--reason",
        "Authenticate for envrcctl",
    ]
    assert kwargs["text"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is True


def test_ensure_device_owner_auth_prefers_stderr(monkeypatch, tmp_path: Path) -> None:
    helper_path = tmp_path / "envrcctl-macos-auth"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="out", stderr="auth failed")

    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setenv("ENVRCCTL_MACOS_AUTH_HELPER", str(helper_path))
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(EnvrcctlError) as exc:
        auth.ensure_device_owner_auth("Authenticate for envrcctl")

    assert str(exc.value) == "auth failed"


def test_ensure_device_owner_auth_falls_back_to_stdout(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-macos-auth"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="auth cancelled", stderr="")

    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setenv("ENVRCCTL_MACOS_AUTH_HELPER", str(helper_path))
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(EnvrcctlError) as exc:
        auth.ensure_device_owner_auth("Authenticate for envrcctl")

    assert str(exc.value) == "auth cancelled"


def test_ensure_device_owner_auth_uses_default_error_when_no_output(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-macos-auth"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="", stderr="")

    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setenv("ENVRCCTL_MACOS_AUTH_HELPER", str(helper_path))
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(EnvrcctlError) as exc:
        auth.ensure_device_owner_auth("Authenticate for envrcctl")

    assert str(exc.value) == "Device owner authentication failed."
