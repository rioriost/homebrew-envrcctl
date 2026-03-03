# Threat Model — envrcctl

## Overview
envrcctl manages `.envrc` files via a managed block and stores secrets in the OS key store.
This document enumerates assets, trust boundaries, threat scenarios, and mitigations.

## Assets
- Secret values stored in OS key stores (Keychain / SecretService)
- Secret references in `.envrc` managed block
- Non-secret environment variables (integrity)
- Local filesystem integrity for `.envrc` and parent directories
- CLI output (must not leak secrets)

## Trust Boundaries
- Local filesystem boundary: `.envrc` and its parent directories
- OS key store boundary: Keychain / SecretService
- External command boundary: subprocess invocations (`security`, `secret-tool`, etc.)
- User input boundary: CLI arguments, stdin, environment variables

## Entry Points
- `envrcctl` CLI commands (init/set/unset/get/list/secret/migrate/inject/eval/doctor)
- Environment variables (e.g., backend selection)
- `.envrc` file contents (existing unmanaged content)

## Threats and Mitigations

### 1) Secret disclosure via CLI output
**Threat:** secrets printed in non-inject commands.  
**Mitigations:**
- Only `inject` emits secret values.
- Other outputs mask secrets.
- Error paths redact sensitive values.

### 2) Unsafe writes to `.envrc`
**Threat:** overwriting through symlinks or world-writable files.  
**Mitigations:**
- Reject symlinked `.envrc` paths and symlinked parent directories.
- Refuse writes when `.envrc` is world-writable.
- Atomic write strategy to avoid partial writes.

### 3) Unmanaged secrets outside managed block
**Threat:** plaintext secrets in `.envrc`.  
**Mitigations:**
- `doctor` warns on unmanaged secret refs and suspicious export names.
- `migrate` moves unmanaged exports into managed block.

### 4) Command injection / unsafe subprocess usage
**Threat:** external commands invoked with attacker-controlled input.  
**Mitigations:**
- Centralized command runner with argument allowlists.
- Validation on user-provided parts for secret refs and environment variables.

### 5) Incorrect backend selection or misuse
**Threat:** silent fallback to unsupported backend.  
**Mitigations:**
- Fail-fast backend selection with explicit errors.
- Scheme validation for secret refs.

## Residual Risks
- Local users with filesystem access can modify `.envrc`.
- OS key store availability and access controls are platform-dependent.

## Operational Guidance
- Keep `.envrc` permissions restrictive (avoid group/world write).
- Prefer `envrcctl secret set` for sensitive values.
- Run `envrcctl doctor` regularly in new repositories.
- Use `./.zed/scripts/verify` and `./.zed/scripts/verify-release` before release.

## Out of Scope
- Remote attackers with no local access.
- OS key store internal vulnerabilities.