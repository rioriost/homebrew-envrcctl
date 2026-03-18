# envrcctl 0.2.0 Implementation Plan: Tamper-Evident Audit Log

## Goal

Add an `audit` feature to `envrcctl` that records secret access events in a **tamper-evident** local audit log.

This feature is intended to answer questions such as:

- which secret refs were accessed
- when they were accessed
- via which `envrcctl` action
- from which working directory
- for `exec`, which command was launched

The design must preserve the existing security posture:

- never store plaintext secret values
- make audit records difficult to alter silently
- keep storage local and protected by filesystem permissions
- provide a readable audit CLI

## Non-Goals

The following are explicitly out of scope for 0.2.0:

- proving that a child process actually consumed a secret after injection
- remote logging / centralized audit aggregation
- storing audit data in Keychain / SecretService
- cryptographic signing with external keys
- multi-user / multi-host correlation
- live streaming or daemon-based monitoring

## High-Level Design

Use a local **append-only JSONL audit log** with a **hash chain** so that any removal or modification of prior entries can be detected later.

Each audit event contains:

- normalized event metadata
- `prev_hash`
- `hash`

The `hash` is computed from the canonical serialized event content excluding the `hash` field itself.

This gives **tamper evidence**, not tamper prevention.

## Why Tamper-Evident Instead of Keychain-Backed Logs

For 0.2.0, local file-backed storage is preferred because it is:

- append-friendly
- easy to inspect and verify
- straightforward to filter and paginate
- independent of interactive auth prompts

Keychain / SecretService are good for secrets, but poor fits for an append-only searchable audit trail.

## Storage Location

Platform-specific state directory:

- macOS:
  - `~/Library/Application Support/envrcctl/audit/`
- Linux:
  - `~/.local/state/envrcctl/audit/`

### Initial file layout

```/dev/null/audit-layout.txt#L1-6
audit/
  audit.jsonl
  latest_hash
  meta.json
```

### Permissions

- directory: `0700`
- files: `0600`

If permissions are weaker than expected:

- writes should fail closed where practical
- `doctor` should warn clearly

## Audit Event Model

Each line in `audit.jsonl` is one JSON object.

### Proposed event schema

```/dev/null/audit-event.json#L1-22
{
  "schema_version": 1,
  "event_id": "uuid",
  "timestamp": "2026-03-18T12:34:56Z",
  "action": "exec",
  "status": "success",
  "vars": ["UV_PUBLISH_TOKEN"],
  "refs": [
    {
      "scheme": "kc",
      "service": "st.rio.envrcctl",
      "account": "uv_token_envrcctl",
      "kind": "runtime"
    }
  ],
  "cwd": "/Users/rifujita/ownCloud/bin/envrcctl",
  "platform": "darwin",
  "command": ["uv", "publish"],
  "reason": null,
  "error": null,
  "prev_hash": "hex-string-or-null",
  "hash": "hex-string"
}
```

## Field Semantics

### Required fields

- `schema_version`
- `event_id`
- `timestamp`
- `action`
- `status`
- `vars`
- `refs`
- `cwd`
- `platform`
- `prev_hash`
- `hash`

### Optional fields

- `command`
  - only meaningful for `exec`
- `reason`
  - optional human-readable note if useful
- `error`
  - set on failure or cancellation

### `action` values for 0.2.0

- `secret_get`
- `inject`
- `exec`

### `status` values

- `success`
- `failure`
- `cancelled`

## Security Rules

### Never log

- secret plaintext values
- clipboard contents
- stdin secret input
- full environment dumps
- auth tokens embedded in failure text unless redacted

### Allowed to log

- variable names
- ref metadata (`scheme`, `service`, `account`, `kind`)
- working directory
- command argv for `exec`
- high-level error category/message after redaction

## Hash Chain Design

### Canonical hash input

For each event:

1. construct the event object without the `hash` field
2. serialize using canonical JSON:
   - UTF-8
   - sorted keys
   - no insignificant whitespace
3. compute `sha256`
4. store hex digest as `hash`

### Chain rule

- first event: `prev_hash = null`
- every subsequent event: `prev_hash = previous_event.hash`

### Verification

`envrcctl audit verify` should:

- read the log sequentially
- recompute each event hash
- confirm every `prev_hash`
- report the first mismatch with file offset / line number / event id

### What tampering becomes detectable

- line modification
- line deletion
- line reordering
- line insertion into the middle

### What is still possible

- deleting the whole audit file
- deleting the latest portion and resetting sidecar metadata
- host-level compromise

For 0.2.0 this is acceptable and should be documented honestly.

## Commands to Add

Create a new `audit` Typer sub-app.

### `envrcctl audit list`

Show recent events in compact form.

Example output:

```/dev/null/audit-list.txt#L1-4
2026-03-18T12:34:56Z  exec        success    UV_PUBLISH_TOKEN      uv publish
2026-03-18T12:33:10Z  secret_get  success    OPENAI_API_KEY
2026-03-18T12:31:00Z  inject      success    TOKEN,OTHER
```

#### Suggested options

- `--limit N`
- `--action <action>`
- `--var <ENV_VAR>`
- `--status <status>`
- `--json`

### `envrcctl audit show`

Show a single event in detail.

#### Suggested options

- `--event-id <uuid>`
- `--index <n>`
- `--json`

### `envrcctl audit verify`

Verify chain integrity and file permissions.

Example output:

```/dev/null/audit-verify.txt#L1-3
OK
events: 128
latest_hash: abcdef...
```

On failure:

```/dev/null/audit-verify-fail.txt#L1-4
FAIL
line: 42
event_id: 123e4567-e89b-12d3-a456-426614174000
reason: hash mismatch
```

### Optional but useful for 0.2.0

- `envrcctl audit path`
- `envrcctl audit tail`

## Event Recording Points

### 1. `secret get`

Record after access attempt is resolved.

#### success event
- action: `secret_get`
- status: `success`
- vars: `[VAR]`
- refs: `[ref]`

#### failure/cancel event
- action: `secret_get`
- status: `failure` or `cancelled`
- error: normalized message

### 2. `inject`

Record once per invocation, not once per secret.

#### success event
- action: `inject`
- vars: all injected runtime vars
- refs: all runtime refs included in the operation

#### failure/cancel event
- record attempted vars/refs if known

### 3. `exec`

Record once per invocation.

#### success event
- action: `exec`
- vars: injected vars
- refs: injected refs
- command: child argv
- status:
  - `success` when child returns `0`
  - `failure` when child returns non-zero or secret resolution fails
  - `cancelled` when auth is cancelled

## Error Classification

Normalize common failures into coarse categories.

### Suggested categories

- `auth_cancelled`
- `auth_unavailable`
- `helper_missing`
- `secret_not_found`
- `invalid_audit_store`
- `command_failed`
- `unknown_error`

This can be represented either as:

```/dev/null/error-structured.json#L1-5
{
  "code": "secret_not_found",
  "message": "The specified item could not be found in the keychain."
}
```

or just as a redacted string in 0.2.0 if keeping it simpler is preferable.

Recommendation: include both `code` and `message`.

## Module / File Changes

### New files

- `src/envrcctl/audit.py`
- `tests/test_audit.py`

### Files to update

- `src/envrcctl/cli.py`
  - register `audit` subcommands
  - call audit recording in `secret get`, `inject`, `exec`
- `src/envrcctl/doctor` logic inside `cli.py`
  - add audit store checks
- `README.md`
- `README.jp.md`
- maybe `docs/security_command_inventory.md`
- maybe `docs/threat_model.md`

## Internal API Proposal

### `src/envrcctl/audit.py`

Suggested API surface:

```/dev/null/audit-api.py#L1-24
@dataclass(frozen=True)
class AuditRef:
    scheme: str
    service: str
    account: str
    kind: str

@dataclass(frozen=True)
class AuditEvent:
    schema_version: int
    event_id: str
    timestamp: str
    action: str
    status: str
    vars: list[str]
    refs: list[AuditRef]
    cwd: str
    platform: str
    command: list[str] | None
    error: dict[str, str] | None
    prev_hash: str | None
    hash: str

def append_event(...)
def iter_events(...)
def verify_chain(...)
def audit_dir(...)
def audit_file(...)
def latest_hash_file(...)
def ensure_audit_store_secure(...)
```

## Logging Strategy

### Recommended approach

Record from the CLI layer after refs are known and just before/after user-visible outcomes are finalized.

This keeps audit semantics aligned with the user's action.

### Important detail

Do not let audit write failures silently break the main secret path without a conscious policy decision.

Recommended 0.2.0 policy:

- default: **fail closed**
  - if audit logging is configured and cannot be written securely, abort sensitive access
- optional future flag:
  - degraded mode / best-effort audit

For 0.2.0, fail-closed is more consistent with the feature's intent.

## Doctor Integration

Extend `doctor` to check:

- audit directory exists or can be created
- permissions are secure
- audit file permissions are secure
- hash chain verifies
- optional warning if audit log is growing large

Example warning:

```/dev/null/doctor-audit-warn.txt#L1-2
WARN: audit chain verification failed at line 42.
WARN: audit directory permissions are too broad; expected 0700.
```

## Migration / Compatibility

Since this is a new feature in 0.2.0:

- no old audit format must be migrated
- initialize empty audit store lazily on first write
- use `schema_version = 1`

Future versions can migrate by:
- reading old events
- rewriting into a new file
- preserving prior chain metadata if desired

## Test Plan

### `tests/test_audit.py`

Cover at least:

- audit path resolution for macOS and Linux
- secure directory/file creation
- append first event
- append subsequent event with correct `prev_hash`
- verify success on clean chain
- detect modified line
- detect missing line
- reject insecure permissions
- redact error payloads if needed

### CLI coverage additions

Cover:

- `secret get` success/failure emits audit event
- `inject` success/failure emits audit event
- `exec` success/failure emits audit event
- audit subcommands render expected output
- `audit verify` failure path

## Suggested Implementation Order

### Slice 1: storage + chain core
- add `audit.py`
- implement path helpers
- implement append-only JSONL writer
- implement canonical hash function
- implement chain verify

### Slice 2: CLI write integration
- wire `secret get`
- wire `inject`
- wire `exec`

### Slice 3: read commands
- `audit list`
- `audit show`
- `audit verify`

### Slice 4: doctor integration
- permissions
- chain verification warnings

### Slice 5: docs
- README
- README.jp
- security notes
- examples

## Open Decisions

### 1. Fail-closed vs best-effort audit writes
Recommendation for 0.2.0:
- fail closed

### 2. Record failed auth attempts?
Recommendation:
- yes

### 3. Record `command` in full for `exec`?
Recommendation:
- yes, but redact obvious secret-like argv values only if ever passed manually

### 4. One log file or rotated files?
Recommendation for 0.2.0:
- one file: `audit.jsonl`
- leave rotation for later

## Example UX

### Successful exec

```/dev/null/example-exec.txt#L1-2
$ envrcctl exec -- uv publish
$ envrcctl audit list --limit 1
```

```/dev/null/example-exec-out.txt#L1-1
2026-03-18T12:34:56Z  exec  success  UV_PUBLISH_TOKEN  uv publish
```

### Verify audit chain

```/dev/null/example-verify.txt#L1-1
$ envrcctl audit verify
```

```/dev/null/example-verify-out.txt#L1-1
OK
```

## Release Notes Draft for 0.2.0

Proposed summary:

- add tamper-evident local audit logging for `secret get`, `inject`, and `exec`
- add `envrcctl audit list/show/verify`
- extend `doctor` with audit integrity and permission checks
- maintain strict policy of never logging plaintext secret values

## Acceptance Criteria

0.2.0 is complete when:

- audit events are written for `secret get`, `inject`, `exec`
- logs contain no plaintext secret values
- each event is chained with `prev_hash` and `hash`
- `envrcctl audit list` works
- `envrcctl audit verify` detects tampering
- audit storage is permission-checked
- docs explain behavior and limitations
- tests cover core audit logic and CLI integration

## Notes for Implementation

- keep the first version intentionally small and explicit
- prefer deterministic JSON serialization everywhere
- keep command output simple by default
- do not hide limitations; describe tamper evidence honestly
- avoid mixing unrelated refactors into the audit feature branch