# External Command Inventory (Security Hardening)

This document inventories all external command invocations to support Phase 5
security hardening work. It focuses on command names, argument structure, and
data sources that may carry untrusted or sensitive data.

## Summary

- External command usage is limited to secret backends:
  - macOS Keychain: `/usr/bin/security`
  - Linux SecretService: `secret-tool`

## Command Inventory

### macOS Keychain (`envrcctl/keychain.py`)

**Runner:** `_run_security(args, input_text=None)`  
**Invocation method:** `subprocess.run(..., text=True, capture_output=True, check=True)`

1) **Get secret**
- **Command:** `security find-generic-password -s <service> -a <account> -w`
- **Dynamic inputs:** `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** No
- **Output:** Secret value on stdout

2) **Set secret**
- **Command:** `security add-generic-password -s <service> -a <account> -U -w`
- **Dynamic inputs:** `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** Yes (`value + "\n"`)
- **Output:** None (success via exit code)

3) **Delete secret**
- **Command:** `security delete-generic-password -s <service> -a <account>`
- **Dynamic inputs:** `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** No
- **Output:** None (success via exit code)

**Error handling:** Exceptions map stderr/stdout to `EnvrcctlError` with fallback
message `"Keychain command failed."`

---

### Linux SecretService (`envrcctl/secretservice.py`)

**Runner:** `_run_secret_tool(args, input_text=None)`  
**Invocation method:** `subprocess.run(..., text=True, capture_output=True, check=True)`

1) **Get secret**
- **Command:** `secret-tool lookup service <service> account <account>`
- **Dynamic inputs:** `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** No
- **Output:** Secret value on stdout

2) **Set secret**
- **Command:** `secret-tool store --label <label> service <service> account <account>`
- **Dynamic inputs:** `label` (derived from `ref.service`/`ref.account`), `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** Yes (`value + "\n"`)
- **Output:** None (success via exit code)

3) **Delete secret**
- **Command:** `secret-tool clear service <service> account <account>`
- **Dynamic inputs:** `ref.service`, `ref.account`
- **Sensitive data in args:** No
- **Sensitive data in stdin:** No
- **Output:** None (success via exit code)

**Error handling:** Exceptions map stderr/stdout to `EnvrcctlError` with fallback
message `"SecretService command failed."`

---

## Security Notes

- All secret values are sent via stdin, not command-line arguments.
- Secret outputs are only expected from `get`/`lookup` paths.
- Error messages may include stderr/stdout from external tools; this should be
  reviewed for potential leakage in Phase 5 hardening.