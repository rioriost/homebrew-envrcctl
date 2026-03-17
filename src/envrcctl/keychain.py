from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .command_runner import run_command
from .errors import EnvrcctlError
from .secrets import SecretBackend, SecretRef


class KeychainBackend(SecretBackend):
    """macOS Keychain backend using /usr/bin/security."""

    HELPER_ENV_VAR = "ENVRCCTL_MACOS_AUTH_HELPER"
    DEFAULT_HELPER_BASENAME = "envrcctl-macos-auth"

    def _helper_path(self) -> Path:
        configured = os.getenv(self.HELPER_ENV_VAR)
        if configured:
            return Path(configured).expanduser()
        return Path(__file__).resolve().parent / self.DEFAULT_HELPER_BASENAME

    def _build_auth_reason(self, action: str, ref: SecretRef) -> str:
        return (
            f"envrcctl needs device owner authentication to {action} "
            f"the secret for {ref.account}."
        )

    def get_with_auth(self, ref: SecretRef, reason: str | None = None) -> str:
        helper_path = self._helper_path()
        if not helper_path.exists():
            raise EnvrcctlError(
                "macOS authentication helper not found. "
                "Build or install envrcctl-macos-auth to use authenticated secret access."
            )
        if not helper_path.is_file():
            raise EnvrcctlError(
                "macOS authentication helper path is invalid. "
                "Expected an executable file."
            )
        if not os.access(helper_path, os.X_OK):
            raise EnvrcctlError(
                "macOS authentication helper is not executable. "
                "Fix permissions and retry."
            )

        result = run_command(
            [
                str(helper_path),
                "--service",
                ref.service,
                "--account",
                ref.account,
                "--reason",
                reason or self._build_auth_reason("access", ref),
            ],
            allowed_commands={str(helper_path)},
            error_message="Authenticated Keychain command failed.",
        )
        return result.rstrip("\n")

    def get(self, ref: SecretRef) -> str:
        result = run_command(
            [
                "security",
                "find-generic-password",
                "-s",
                ref.service,
                "-a",
                ref.account,
                "-w",
            ],
            allowed_commands={"security"},
            error_message="Keychain command failed.",
        )
        return result.strip()

    def set(self, ref: SecretRef, value: str) -> None:
        # Pass password directly to avoid interactive prompt.
        run_command(
            [
                "security",
                "add-generic-password",
                "-s",
                ref.service,
                "-a",
                ref.account,
                "-U",
                "-w",
                value,
            ],
            input_text=value,
            allowed_commands={"security"},
            error_message="Keychain command failed.",
        )

    def delete(self, ref: SecretRef) -> None:
        run_command(
            [
                "security",
                "delete-generic-password",
                "-s",
                ref.service,
                "-a",
                ref.account,
            ],
            allowed_commands={"security"},
            error_message="Keychain command failed.",
        )

    def list(self, prefix: str | None = None) -> List[SecretRef]:
        # Keychain listing is not required for Phase 1 use-cases.
        return []
