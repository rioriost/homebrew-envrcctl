# macOS Device Owner Authentication Plan

## Version
- plan_id: `macos-device-owner-auth-v2`
- status: `planned`
- scope: `macOS auth hardening for secret get / inject`
- source: `docs/macos_device_owner_auth_plan.md`

## Goal

Harden `envrcctl` on macOS so that sensitive secret-accessing commands require both:

1. the existing `_is_interactive()` check, and
2. successful macOS device owner authentication

The target behavior is:

- on **macOS**
  - `envrcctl secret get ...`
  - `envrcctl inject`
  require `_is_interactive()` **and** Touch ID / Apple Watch / other OS-managed device owner authentication through macOS
- on **Linux**
  - current behavior remains
  - `_is_interactive()` stays the protection mechanism for these commands

## Problem Statement

Today, `_is_interactive()` is used as a gate for sensitive output paths, but TTY-based detection is not a strong security boundary on macOS. AI agents, IDE PTYs, and other automated environments may still appear interactive.

For macOS secret access flows, the security boundary should be strengthened so that:

1. TTY presence alone is not sufficient
2. macOS performs a device owner approval step
3. commands fail closed when authentication is unavailable or cancelled
4. Linux behavior remains unchanged for now

## Commands in Scope

### macOS
The following commands must require both `_is_interactive()` and device owner authentication:

- `envrcctl secret get`
- `envrcctl inject`

### Linux
The following commands keep current behavior:

- `envrcctl secret get`
- `envrcctl inject`

On Linux, these commands remain guarded by `_is_interactive()` and existing force/plain options where currently supported.

## Desired User-Facing Behavior

## macOS: `secret get`

### Baseline rule
On macOS, `secret get` must not reveal or copy a secret unless:

- `_is_interactive()` returns true
- device owner authentication succeeds

### Detailed behavior
- If `_is_interactive()` is false:
  - preserve current behavior of blocking the command unless the existing override policy explicitly allows it
  - however, even where an override exists today, macOS plaintext/copy access should not bypass authentication requirements
- If `_is_interactive()` is true:
  - macOS device owner authentication is required before:
    - printing plaintext
    - copying to clipboard
    - returning the value through any user-facing reveal path
- If authentication is cancelled or unavailable:
  - no secret is printed
  - no secret is copied to the clipboard
  - the command exits with an error

### Resulting security model
On macOS, `_is_interactive()` becomes a **necessary but not sufficient** condition for `secret get`.

## macOS: `inject`

### Baseline rule
On macOS, `inject` must not emit secret export lines unless:

- `_is_interactive()` returns true, and
- device owner authentication succeeds

### Detailed behavior
- Existing `_is_interactive()` behavior stays in place
- `--force` must not bypass macOS device owner authentication
- Even if `--force` remains relevant for Linux/non-macOS behavior, macOS must still require OS authentication before emitting exports
- If authentication is cancelled or unavailable:
  - no export lines are emitted
  - the command exits with an error

### Resulting security model
On macOS, `_is_interactive()` plus OS authentication are both required before `inject` outputs secret material.

## Linux Behavior

Linux remains unchanged in this plan.

That means:

- `_is_interactive()` remains the gate for `secret get` and `inject`
- existing Linux-friendly behavior and flags are preserved
- no native device owner authentication equivalent is introduced in this work

This keeps the change scoped and avoids mixing the macOS hardening project with Linux authentication design.

## Technical Direction

## Authentication boundary on macOS

Use macOS device owner authentication rather than relying only on application-level interactivity checks.

Recommended policy:

- `.deviceOwnerAuthentication`

Reason:

- supports Touch ID where available
- allows macOS to offer Apple Watch approval when supported by host configuration
- allows OS-managed fallback behavior
- models “the device owner approved this action”

The implementation should not promise a specific factor. The requirement is:

- successful macOS device owner authentication

## Native bridge

Implement a small Swift helper that:

1. receives service/account input and operation context
2. creates an `LAContext`
3. evaluates `.deviceOwnerAuthentication`
4. reads the Keychain item using the authentication context
5. returns the secret only after successful OS authentication
6. emits sanitized failure output on error

For `inject`, the helper may be called once per secret ref or through a higher-level authenticated retrieval flow coordinated by Python, depending on the implementation that best balances simplicity and UX.

## Python integration

Integrate authenticated retrieval into the macOS Keychain backend.

Preferred shape:

- keep existing `get(ref)` behavior for generic backend semantics where needed
- add an authenticated retrieval path for macOS, such as `get_with_auth(ref, reason=...)`
- require macOS `secret get` and `inject` flows to use the authenticated path
- keep Linux backend behavior unchanged

## Architecture Decisions

### Decision 1: Keep `_is_interactive()` on macOS
Rationale:

- preserves current UX expectations
- still distinguishes interactive from non-interactive shell use
- avoids broad behavior changes outside the specific hardening goal

### Decision 2: Add macOS device owner authentication on top of `_is_interactive()`
Rationale:

- TTY checks alone are insufficient on macOS
- OS-level approval provides a stronger boundary against automated callers
- preserves Linux behavior while strengthening macOS only

### Decision 3: Apply auth to `secret get` and `inject`
Rationale:

- both commands can expose secret material to the caller
- both are currently TTY-sensitive
- hardening should cover the actual secret-output paths in scope

### Decision 4: Do not rely on `--force` or plaintext flags to bypass auth on macOS
Rationale:

- auth should be the real security boundary
- CLI discoverability and flags must not imply access
- existing override flags may remain for Linux compatibility, but must not weaken macOS behavior

## Command-Level Policy

## `secret get`

### macOS
Require:

- `_is_interactive() == True`
- successful device owner authentication

Applies to:

- masked/clipboard default path before clipboard copy
- `--plain`
- `--show`
- `--force-plain`
- any other path that returns the secret to the caller

### Linux
Keep current behavior.

## `inject`

### macOS
Require:

- `_is_interactive() == True`
- successful device owner authentication

Applies to:

- normal `inject`
- `inject --force`

### Linux
Keep current behavior.

## Error Handling Policy

## macOS failure cases

The following must fail closed:

- not interactive
- authentication unavailable
- authentication cancelled
- helper missing
- unsupported helper/runtime state
- Keychain item missing
- Keychain read failure

Fail-closed means:

- no plaintext secret output
- no clipboard copy
- no export line emission
- non-zero exit status
- concise, sanitized error message

## Linux failure cases

Linux keeps current error semantics for `_is_interactive()`-guarded behavior.

## Implementation Phases

## Phase 1 — CLI Contract Update
### Objectives
- redefine the target behavior around `secret get` and `inject`
- preserve Linux behavior
- make macOS requirements explicit

### Tasks
1. Update command contract for macOS `secret get`
2. Update command contract for macOS `inject`
3. Define exact interaction of:
   - `_is_interactive()`
   - `--plain`
   - `--show`
   - `--force-plain`
   - `--force`
4. Define fail-closed messaging for auth failures
5. Define README wording for macOS vs Linux differences

### Outputs
- finalized command policy for `secret get`
- finalized command policy for `inject`
- clear macOS/Linux behavior split
- error message catalog

### Exit Criteria
- command behavior is fully specified
- no ambiguity remains around force/plain flags on macOS
- docs wording direction is settled

## Phase 2 — Native macOS Authentication Helper
### Objectives
- build a minimal Swift helper for authenticated Keychain reads

### Tasks
1. Add helper source in a packaging-friendly location
2. Implement:
   - `Foundation`
   - `LocalAuthentication`
   - `Security`
3. Create `LAContext`
4. Check `.deviceOwnerAuthentication` availability
5. Evaluate policy with a localized reason
6. Read generic password item using the authentication context
7. Return the secret only on success
8. Return short sanitized errors on failure
9. Ensure no secret material appears in diagnostics
10. Document local build instructions

### Outputs
- Swift helper source
- helper CLI contract
- local build instructions
- failure mapping

### Exit Criteria
- helper can retrieve a secret after successful macOS auth
- cancellation and failure are distinguishable
- failure output contains no secret material

## Phase 3 — Python Backend and CLI Integration
### Objectives
- wire authenticated retrieval into macOS `secret get` and `inject`

### Tasks
1. Add authenticated retrieval method/path in the macOS backend
2. Integrate helper invocation from Python
3. Update `secret get` so macOS requires:
   - `_is_interactive()`
   - device owner authentication
4. Update `inject` so macOS requires:
   - `_is_interactive()`
   - device owner authentication
5. Ensure `--force` on macOS does not bypass authentication
6. Ensure plaintext/copy paths on macOS do not bypass authentication
7. Preserve Linux behavior

### Outputs
- backend integration code
- updated macOS `secret get`
- updated macOS `inject`
- preserved Linux code paths

### Exit Criteria
- macOS `secret get` requires both checks
- macOS `inject` requires both checks
- Linux behavior remains unchanged
- no unauthenticated macOS secret output path remains in scope

## Phase 4 — Tests and Verification
### Objectives
- add automated coverage for Python-side behavior
- add manual verification for macOS auth UX

### Tasks
1. Add CLI tests for macOS/non-macOS behavior split
2. Add tests for `secret get`:
   - not interactive
   - auth success
   - auth cancelled
   - auth unavailable
   - helper missing
3. Add tests for `inject`:
   - not interactive
   - auth success
   - auth cancelled
   - auth unavailable
   - helper missing
4. Add tests confirming macOS `--force` does not bypass auth
5. Add tests confirming Linux behavior remains unchanged
6. Add manual macOS verification checklist:
   - Touch ID success for `secret get`
   - Touch ID success for `inject`
   - cancel flow for both
   - Apple Watch-assisted approval where supported
   - no output on failure

### Outputs
- automated Python-side tests
- manual verification checklist

### Exit Criteria
- macOS behavior is covered by tests and manual steps
- Linux behavior regression coverage exists
- failure cases are verified to produce no secret output

## Phase 5 — Documentation and Rollout
### Objectives
- document the new macOS behavior clearly
- explain platform differences
- avoid confusing users about force/plain flags

### Tasks
1. Update `README.md`
2. Update `README.jp.md` if maintained in parallel
3. Document that on macOS:
   - `secret get` requires `_is_interactive()` and device owner authentication
   - `inject` requires `_is_interactive()` and device owner authentication
   - Touch ID / Apple Watch availability depends on macOS and device settings
4. Document that on Linux:
   - `_is_interactive()` remains the gate
5. Clarify that `--force` does not bypass macOS authentication for `inject`
6. Clarify how `--plain` / `--show` / `--force-plain` behave on macOS
7. Add troubleshooting for:
   - no auth prompt
   - Touch ID unavailable
   - Apple Watch not offered
   - helper missing
   - Keychain access failures

### Outputs
- updated README docs
- platform behavior notes
- troubleshooting guidance

### Exit Criteria
- docs match implementation intent
- platform differences are explicit
- users can understand why macOS requires extra approval

## README Update Requirements

The README changes for this plan must explain all of the following:

1. On macOS, `secret get` requires:
   - an interactive shell, and
   - device owner authentication
2. On macOS, `inject` requires:
   - an interactive shell, and
   - device owner authentication
3. On Linux, both commands continue to use `_is_interactive()`-based protection only
4. Touch ID and Apple Watch are not app-selectable guarantees; they are OS-managed outcomes of device owner authentication
5. `--force` on macOS does not bypass authentication for `inject`
6. Any plaintext reveal/copy path in `secret get` on macOS also requires authentication

Suggested README wording direction:

- keep feature summary concise
- add a dedicated platform/security note section
- mention Apple Watch as “if offered by macOS” rather than a guaranteed prompt option

## Risks

### Risk: multiple auth prompts during `inject`
Mitigation:
- decide whether to authenticate once per command or per secret access path where feasible
- optimize UX without weakening the security model

### Risk: user confusion around `--force`
Mitigation:
- document clearly that `--force` does not bypass macOS authentication
- preserve its Linux meaning if appropriate

### Risk: Apple Watch behavior varies by host setup
Mitigation:
- promise only device owner authentication
- describe Apple Watch as OS-dependent behavior

### Risk: current Keychain items are not item-level auth-bound
Mitigation:
- ship helper-enforced gating first
- evaluate item-level protection in a later hardening phase if needed

## Open Questions
1. On macOS `secret get`, should clipboard copy authenticate once per command or once per secret retrieval path?
2. On macOS `inject`, should authentication happen once before resolving all runtime secrets, or separately for each secret access?
3. Should `secret get --force-plain` on macOS be retained as a syntactic alias with auth, or simplified later?
4. Should `README.jp.md` be updated in the same change set as `README.md`?
5. Should a later phase migrate macOS-stored secrets to item-level access control?

## Acceptance Criteria

This plan is complete when:

- on macOS, `secret get` requires `_is_interactive()` and successful device owner authentication
- on macOS, `inject` requires `_is_interactive()` and successful device owner authentication
- on Linux, `secret get` and `inject` remain `_is_interactive()`-guarded without new OS auth requirements
- no macOS `secret get` output path in scope reveals or copies secret data after auth failure/cancellation
- no macOS `inject` path emits export lines after auth failure/cancellation
- README documentation clearly explains the macOS/Linux behavior split
- tests and manual verification cover both command paths

## Recommended Next Step

Start with:

1. finalize the macOS command contract for `secret get`
2. finalize the macOS command contract for `inject`
3. update README wording requirements
4. implement the native helper
5. integrate helper checks into the macOS backend and CLI

This sequence preserves Linux behavior while hardening the two macOS commands that currently depend on `_is_interactive()`.