# macOS Device Owner Authentication Implementation Plan

## Goal

Harden `envrcctl` secret reveal flows on macOS by requiring OS-level device owner authentication instead of relying on TTY-based interactivity checks. This should allow Touch ID and, where supported by the OS and user settings, Apple Watch / password-backed authentication via macOS authentication policy.

## Background

Current secret access control in `envrcctl` relies in part on whether the process appears interactive. That is insufficient because AI agents, IDE terminals, and PTY-backed automation can still satisfy TTY checks.

The stronger design is to move secret reveal authorization to macOS authentication primitives:

- Keychain access guarded by macOS
- LocalAuthentication policy evaluation
- Device owner authentication (`deviceOwnerAuthentication`) rather than app-local heuristics

This makes secret retrieval depend on a system-level authentication event rather than whether the caller can allocate a terminal.

## Scope

In scope:

- macOS-only hardening path for plaintext secret reveal
- New authenticated reveal path using device owner authentication
- Python-to-native bridge for authenticated Keychain reads
- CLI behavior changes for `secret get` / `secret reveal`
- Tests, docs, and rollout notes

Out of scope:

- Linux backend changes
- Attempting to detect AI agents directly
- Requiring `sudo`
- Replacing existing Keychain storage model unless needed for authenticated access

## Design Summary

### Current state

- `KeychainBackend` uses `/usr/bin/security`
- `secret get` can print plaintext under some conditions
- Non-interactive protection is based on TTY heuristics

### Target state

- Plaintext reveal is separated from ordinary secret access UX
- `secret get` defaults to masked/clipboard-safe behavior only
- New `secret reveal` path requires macOS device owner authentication
- macOS backend uses a small native helper built with Swift
- Native helper uses:
  - `LocalAuthentication`
  - `Security`
  - `LAContext`
  - Keychain query with authentication context
- Authentication policy should be `.deviceOwnerAuthentication`

This allows macOS to choose an appropriate authentication mechanism, such as:

- Touch ID
- Apple Watch approval, if enabled by the OS/user configuration
- Password/passcode fallback, when applicable

## Why `.deviceOwnerAuthentication`

Use `.deviceOwnerAuthentication` instead of biometrics-only authentication.

Reasons:

- Supports Touch ID when available
- Allows OS-managed fallback behavior
- More compatible with Apple Watch-based unlock/approval paths
- Avoids hard-failing on systems without biometric-only capability

We are not trying to force a specific factor. We want macOS to enforce "a device owner approved this action."

## Proposed CLI Changes

### 1. Add `secret reveal`

Introduce a dedicated command for plaintext output:

- `envrcctl secret reveal VAR`

Behavior:

- macOS only
- Requires device owner authentication
- Prints plaintext only after successful OS authentication
- Fails closed if authentication cannot be performed

### 2. Narrow `secret get`

Change `secret get` behavior so it no longer acts as the main plaintext reveal path.

Recommended behavior:

- default: masked value or clipboard-only
- `--plain` and `--show`: deprecate, then remove
- `--force-plain`: deprecate, then remove

Short-term compatibility option:

- Keep existing flags temporarily
- On macOS, route them through the same authenticated reveal path
- Emit deprecation guidance toward `secret reveal`

### 3. Leave `inject` and `exec` behavior unchanged for now

These are runtime secret delivery paths, not interactive reveal UX. They may need future hardening, but this plan focuses specifically on plaintext reveal by a human.

## Architecture

## Python layer

Add a new backend capability for authenticated reveal.

Possible interface evolution:

- keep `get(ref)` for non-reveal operational use
- add `get_with_auth(ref)` for human-approved plaintext reveal

Suggested shape:

- `SecretBackend.get(ref)` remains existing behavior
- `KeychainBackend.get_with_auth(ref)` becomes macOS-specific
- callers that need plaintext-to-user output must use `get_with_auth`

If keeping the protocol minimal is preferred, another option is:

- add a separate helper function in the macOS backend
- keep protocol unchanged
- invoke authenticated reveal only in the CLI reveal command

Recommendation: add an explicit authenticated path to make reveal semantics obvious in code.

## Native helper

Add a small macOS helper executable written in Swift.

Responsibilities:

1. Parse service/account input
2. Create `LAContext`
3. Evaluate `.deviceOwnerAuthentication`
4. Query Keychain with the authentication context
5. Return the secret to stdout only on success
6. Return non-zero exit status with sanitized error text on failure

The helper should not log secret material and should keep output minimal.

## Keychain interaction model

Two implementation options exist.

### Option A: Authenticate before read, use existing generic password items

Flow:

1. Evaluate `LAContext`
2. Read existing generic password item
3. Treat authentication as required app policy

Pros:

- Minimal migration risk
- Existing stored items can continue to work

Cons:

- Depends more on app-side policy than item-level access control
- Weaker than item-level enforcement if helper behavior is bypassed elsewhere

### Option B: Store/retrieve with item-level access control

Flow:

1. Store items with `SecAccessControl`
2. Require user presence / device owner auth at Keychain access time
3. Retrieve with matching authentication context

Pros:

- Stronger OS-enforced protection model
- Better alignment with "secret itself requires auth"

Cons:

- Requires migration from current `/usr/bin/security` item creation flow
- More implementation work
- May require careful handling of update/replace semantics

Recommendation:

- Phase 1 of this change: implement authenticated reveal with native helper over current storage model
- Phase 2: assess migration to item-level access control for stronger enforcement

## Implementation Phases

## Phase 1 — Planning and CLI contract

### Objectives

- Define exact UX for authenticated reveal
- Minimize breaking changes
- Isolate plaintext secret output behind a dedicated command

### Tasks

1. Specify final command UX:
   - `secret reveal VAR`
   - revised `secret get`
   - deprecation behavior for `--plain`, `--show`, `--force-plain`

2. Define failure messages:
   - not on macOS
   - authentication unavailable
   - authentication cancelled
   - Keychain item missing
   - helper not installed

3. Update docs to state:
   - plaintext secret reveal requires macOS authentication
   - Touch ID / Apple Watch availability depends on OS and device settings

### Exit criteria

- CLI behavior is documented
- Compatibility strategy is agreed
- Failure modes are enumerated

## Phase 2 — Native helper implementation

### Objectives

- Build a minimal Swift helper for authenticated Keychain reads

### Tasks

1. Add helper source tree, for example:
   - `native/`
   - or `scripts/macos/`
   - or another packaging-friendly location

2. Implement Swift helper using:
   - `Foundation`
   - `LocalAuthentication`
   - `Security`

3. Authentication flow:
   - create `LAContext`
   - call `canEvaluatePolicy(.deviceOwnerAuthentication, ...)`
   - call `evaluatePolicy(.deviceOwnerAuthentication, localizedReason: ...)`

4. Keychain read flow:
   - construct generic password query
   - include `kSecUseAuthenticationContext`
   - request returned data
   - decode UTF-8 safely

5. Error handling:
   - do not emit stack traces by default
   - map macOS auth failures to short, user-safe messages
   - never print secret material except successful result

6. Build/run instructions:
   - document local compilation
   - define how packaging will include the helper

### Exit criteria

- Helper can authenticate and retrieve a secret by service/account
- Auth cancellation and failure paths are distinguishable
- No secret leaks in error output

## Phase 3 — Python backend integration

### Objectives

- Wire authenticated reveal into `envrcctl`

### Tasks

1. Add backend method or helper path for authenticated retrieval

2. Implement macOS helper invocation from Python:
   - validate executable path
   - pass service/account as arguments
   - capture stdout
   - sanitize stderr exposure

3. Add `secret reveal` command:
   - validate variable name
   - resolve secret ref
   - require Keychain backend
   - call authenticated reveal path
   - print value on success

4. Revise `secret get`:
   - default remains non-plaintext UX
   - optional compatibility flags route through authenticated path
   - emit deprecation notice where applicable

5. Preserve non-macOS behavior:
   - fail clearly if reveal is requested on unsupported platforms

### Exit criteria

- `envrcctl secret reveal VAR` works on macOS
- plaintext reveal requires successful OS authentication
- old plaintext flags are no longer unauthenticated

## Phase 4 — Tests

### Objectives

- Add reliable automated coverage around the new behavior
- Separate unit-testable logic from OS integration concerns

### Tasks

1. Unit tests for CLI behavior:
   - `secret reveal` command routing
   - variable/ref validation
   - unsupported platform errors
   - helper failure mapping
   - deprecation behavior for old plaintext flags

2. Backend tests:
   - helper invocation argument construction
   - stdout/stderr handling
   - non-zero exit code mapping

3. Mocked integration tests:
   - successful authenticated reveal
   - user-cancelled auth
   - helper missing
   - item not found

4. Manual verification checklist on macOS:
   - Touch ID success path
   - auth cancel path
   - auth unavailable path
   - Apple Watch-assisted approval if configured on host
   - no-auth plaintext path is blocked

### Exit criteria

- Automated tests cover non-native Python behavior
- Manual macOS verification checklist is documented and reproducible

## Phase 5 — Documentation and rollout

### Objectives

- Make the new security model understandable and usable

### Tasks

1. Update README / security docs:
   - plaintext reveal requires device owner authentication
   - `secret get` vs `secret reveal`
   - note that Apple Watch support depends on macOS settings

2. Add migration notes:
   - deprecation of `--plain`, `--show`, `--force-plain`
   - no behavior change for stored refs unless later migration is introduced

3. Add troubleshooting guide:
   - helper missing
   - auth prompt not appearing
   - Touch ID unavailable
   - Apple Watch not offered by macOS
   - Keychain item access issues

### Exit criteria

- User docs match shipped behavior
- Security model is explicit
- Rollout path is documented

## Packaging Plan

## Short term

Ship the helper as a local compiled artifact for development and manual testing.

Needs:

- deterministic build instructions
- stable helper path expected by Python
- repository-local documentation

## Medium term

Package the helper with the Python distribution.

Potential approaches:

- build helper during release workflow
- bundle binary in wheel for macOS
- install helper alongside Python package entrypoints

Selection criteria:

- reliable install path
- signed/notarized future compatibility if distribution broadens
- low maintenance burden

## Security Requirements

The implementation must satisfy all of the following:

1. No TTY-only gating for plaintext reveal
2. No secret value in logs, error messages, or exceptions
3. Plaintext output only after successful device owner authentication
4. Unsupported platforms fail closed
5. Missing helper fails closed
6. CLI help may describe reveal behavior, but discoverability must not grant access
7. Authentication must be OS-mediated, not app-simulated
8. Authentication cancellation must not fall back to plaintext output

## Risks and Mitigations

### Risk: native helper adds packaging complexity

Mitigation:

- keep helper small and single-purpose
- isolate macOS-only logic there
- document build and install path clearly

### Risk: Apple Watch behavior is inconsistent across systems

Mitigation:

- do not promise Apple Watch specifically
- document that `.deviceOwnerAuthentication` allows OS-selected approval methods
- test for "device owner authentication succeeded" rather than a specific factor

### Risk: current Keychain item creation is not item-level auth bound

Mitigation:

- ship reveal gating first
- separately evaluate migration to `SecAccessControl`-protected items

### Risk: old flags still imply unsafe legacy behavior

Mitigation:

- route them through authenticated reveal immediately
- deprecate them in docs and CLI help
- remove them in a later cleanup release

## Open Questions

1. Should `secret get --plain` remain as an authenticated alias, or be removed immediately?
2. Should clipboard copy remain available without device owner auth?
3. Should `inject` / `exec` later gain optional device owner auth modes for especially sensitive refs?
4. Should newly stored secrets eventually migrate to item-level access control instead of helper-only gating?
5. What is the preferred repository location and build path for the Swift helper?

## Recommended Deliverables

- `docs/macos_device_owner_auth_plan.md`
- Swift helper source
- Python backend integration for authenticated reveal
- `secret reveal` CLI command
- updated README/security docs
- unit tests and manual verification checklist

## Acceptance Criteria

This work is complete when:

- `envrcctl secret reveal VAR` exists on macOS
- plaintext secret reveal requires successful device owner authentication
- Touch ID works where supported
- Apple Watch approval is possible where macOS offers it through device owner authentication
- unauthenticated TTY-based plaintext reveal is no longer possible
- tests and docs reflect the new model

## Recommended Next Step

Implement Phase 1 and Phase 2 first:

1. finalize CLI contract
2. build the Swift helper
3. manually verify authentication UX on macOS
4. then wire it into `secret reveal`

This sequencing minimizes migration risk while moving plaintext reveal onto an OS-enforced security boundary.