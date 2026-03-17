from __future__ import annotations

import json
import subprocess
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from envrcctl.errors import EnvrcctlError
from envrcctl.keychain import KeychainBackend
from envrcctl.secrets import SecretRef


class DummyResult:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout
        self.stderr = ""


def test_keychain_get_calls_security(monkeypatch) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult(stdout="secret\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    value = backend.get(ref)
    assert value == "secret"
    assert calls[0][0][:3] == ["security", "find-generic-password", "-s"]
    assert "-a" in calls[0][0]
    assert "-w" in calls[0][0]


def test_keychain_set_passes_password_arg(monkeypatch) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    backend.set(ref, "value")
    args, kwargs = calls[0]
    assert args[:3] == ["security", "add-generic-password", "-s"]
    assert "-U" in args
    assert args[-2:] == ["-w", "value"]
    assert kwargs["input"] == "value"


def test_keychain_delete_calls_security(monkeypatch) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    backend.delete(ref)
    args, _ = calls[0]
    assert args[:2] == ["security", "delete-generic-password"]
    assert "-s" in args
    assert "-a" in args


def test_keychain_error_prefers_stderr(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    with pytest.raises(EnvrcctlError) as exc:
        backend.get(ref)

    assert "err" in str(exc.value)


def test_keychain_error_falls_back_to_stdout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="oops", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    with pytest.raises(EnvrcctlError) as exc:
        backend.get(ref)

    assert "oops" in str(exc.value)


def test_keychain_error_redacts_secret(monkeypatch) -> None:
    secret = "supersecret"

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="", stderr=f"bad {secret} msg")

    monkeypatch.setattr(subprocess, "run", fake_run)

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    with pytest.raises(EnvrcctlError) as exc:
        backend.set(ref, secret)

    assert secret not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)


def test_keychain_helper_path_uses_env_var(monkeypatch, tmp_path: Path) -> None:
    helper_path = tmp_path / "custom-helper"
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()

    assert backend._helper_path() == helper_path


def test_keychain_helper_path_defaults_next_to_module(monkeypatch) -> None:
    monkeypatch.delenv(KeychainBackend.HELPER_ENV_VAR, raising=False)

    backend = KeychainBackend()
    helper_path = backend._helper_path()

    assert helper_path.name == KeychainBackend.DEFAULT_HELPER_BASENAME
    assert helper_path.name


def test_keychain_build_auth_reason() -> None:
    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    reason = backend._build_auth_reason("access", ref)

    assert "access" in reason
    assert "acct" in reason


def test_keychain_get_with_auth_calls_helper(monkeypatch, tmp_path: Path) -> None:
    calls = []

    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult(stdout="secret\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    ref = SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")

    value = backend.get_with_auth(ref, reason="Reveal secret for envrcctl")

    assert value == "secret"
    args, kwargs = calls[0]
    assert args == [
        str(helper_path),
        "--service",
        "svc",
        "--account",
        "acct",
        "--reason",
        "Reveal secret for envrcctl",
    ]
    assert kwargs["input"] is None


def test_keychain_get_many_with_auth_calls_helper_once(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    response = {
        "items": [
            {"service": "svc", "account": "acct1", "value": "secret1"},
            {"service": "svc", "account": "acct2", "value": "secret2"},
        ]
    }

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult(stdout=json.dumps(response))

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [
        SecretRef(scheme="kc", service="svc", account="acct1", kind="runtime"),
        SecretRef(scheme="kc", service="svc", account="acct2", kind="runtime"),
    ]

    values = backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert values == {
        ("svc", "acct1"): "secret1",
        ("svc", "acct2"): "secret2",
    }
    assert len(calls) == 1

    args, kwargs = calls[0]
    assert args == [
        str(helper_path),
        "--input-json",
        "-",
        "--reason",
        "Inject secrets with envrcctl",
    ]
    assert kwargs["input"] is not None

    payload = json.loads(kwargs["input"])
    assert payload == {
        "items": [
            {"service": "svc", "account": "acct1"},
            {"service": "svc", "account": "acct2"},
        ]
    }


def test_keychain_get_many_with_auth_uses_default_reason(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult(
            stdout=json.dumps(
                {"items": [{"service": "svc", "account": "acct", "value": "secret"}]}
            )
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    values = backend.get_many_with_auth(refs)

    assert values == {("svc", "acct"): "secret"}
    args, _ = calls[0]
    assert args[:3] == [str(helper_path), "--input-json", "-"]
    assert args[3] == "--reason"
    assert "acct" in args[4]


def test_keychain_get_many_with_auth_deduplicates_duplicate_refs(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    response = {
        "items": [
            {"service": "svc", "account": "acct", "value": "secret"},
        ]
    }

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return DummyResult(stdout=json.dumps(response))

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [
        SecretRef(scheme="kc", service="svc", account="acct", kind="runtime"),
        SecretRef(scheme="kc", service="svc", account="acct", kind="runtime"),
    ]

    values = backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert values == {("svc", "acct"): "secret"}
    assert len(calls) == 1

    args, kwargs = calls[0]
    assert args == [
        str(helper_path),
        "--input-json",
        "-",
        "--reason",
        "Inject secrets with envrcctl",
    ]
    payload = json.loads(kwargs["input"])
    assert payload == {
        "items": [
            {"service": "svc", "account": "acct"},
        ]
    }


def test_keychain_get_many_with_auth_requires_existing_helper(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "missing-helper"
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "helper" in str(exc.value).lower()


def test_keychain_get_many_with_auth_requires_file_helper(
    monkeypatch, tmp_path: Path
) -> None:
    helper_dir = tmp_path / "helper-dir"
    helper_dir.mkdir()
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_dir))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "invalid" in str(exc.value).lower()


def test_keychain_get_many_with_auth_requires_executable_helper(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o644)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "not executable" in str(exc.value).lower()


def test_keychain_get_many_with_auth_prefers_stderr(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="out", stderr="auth failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "auth failed" in str(exc.value)


def test_keychain_get_many_with_auth_falls_back_to_stdout(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(*args, **kwargs):
        raise CalledProcessError(1, args[0], output="auth cancelled", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "auth cancelled" in str(exc.value)


def test_keychain_get_many_with_auth_rejects_invalid_json(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        return DummyResult(stdout="not-json")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "json" in str(exc.value).lower()


def test_keychain_get_many_with_auth_rejects_missing_values(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        return DummyResult(
            stdout=json.dumps({"items": [{"service": "svc", "account": "acct"}]})
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "value" in str(exc.value).lower()


def test_keychain_get_many_with_auth_rejects_duplicate_entries(
    monkeypatch, tmp_path: Path
) -> None:
    helper_path = tmp_path / "envrcctl-auth-helper"
    helper_path.write_text("#!/bin/sh\n", encoding="utf-8")
    helper_path.chmod(0o755)

    def fake_run(args, **kwargs):
        return DummyResult(
            stdout=json.dumps(
                {
                    "items": [
                        {"service": "svc", "account": "acct", "value": "secret1"},
                        {"service": "svc", "account": "acct", "value": "secret2"},
                    ]
                }
            )
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(KeychainBackend.HELPER_ENV_VAR, str(helper_path))

    backend = KeychainBackend()
    refs = [SecretRef(scheme="kc", service="svc", account="acct", kind="runtime")]

    with pytest.raises(EnvrcctlError) as exc:
        backend.get_many_with_auth(refs, reason="Inject secrets with envrcctl")

    assert "duplicate" in str(exc.value).lower()


def test_keychain_list_returns_empty() -> None:
    backend = KeychainBackend()
    assert backend.list() == []
