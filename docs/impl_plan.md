# envrcctl Implementation Plan

This plan expands `docs/draft.md` into concrete, phased execution steps. Each phase is designed to deliver a coherent set of user-facing capabilities with minimal risk, clear interfaces, and testable outcomes.

---

## Phase 1 — MVP (macOS)

**Goal:** Provide a safe, minimal CLI that manages `.envrc` via a managed block, supports non-secret and secret CRUD, inheritance toggling, and secret injection. Uses macOS Keychain.

### Scope
- CLI skeleton with subcommands: `init`, `set`, `unset`, `list`, `get`, `inherit on/off`, `secret set/unset/list`, `inject`
- Managed block generation and parsing
- Non-secret export CRUD within managed block
- Secret references stored in managed block (no secret values)
- Secret backend interface and Keychain implementation
- Atomic `.envrc` write behavior
- Input handling for secrets (`--prompt` default, `--stdin` optional)

### Deliverables
- Functional CLI for macOS
- Managed block format enforced
- Keychain-backed secret CRUD
- `inject` prints exports for resolved secrets
- Minimal documentation and usage examples

### Implementation Steps
1. **Project layout & CLI entrypoint**
   - Establish Python package structure
   - Choose CLI framework (Typer/Click)
   - Define top-level command and subcommand routing

2. **Managed block module**
   - Define block markers (`# >>> envrcctl:begin` / `# <<< envrcctl:end`)
   - Parse existing `.envrc`
   - Regenerate managed block from internal model
   - Preserve unmanaged content outside block

3. **Model for managed entries**
   - Represent:
     - `inherit` state (`source_up`)
     - non-secret exports
     - secret refs (e.g., `ENVRCCTL_SECRET_<VAR>=<ref>`)
     - `eval "$(envrcctl inject)"` line

4. **Atomic writer**
   - Write to temp file then atomic replace
   - Optional warning if `.envrc` is world-writable

5. **Non-secret CRUD**
   - `set VAR value`
   - `unset VAR`
   - `get VAR`
   - `list`

6. **Secret backend interface**
   - Define `SecretBackend` class with `get/set/delete/list`
   - Implement macOS Keychain backend using `/usr/bin/security`
   - Define ref format: `kc:<service>:<account>`

7. **Secret CRUD**
   - `secret set VAR --account` → set keychain secret + add managed ref
   - `secret unset VAR` → delete keychain secret + remove ref
   - `secret list` → list refs from managed block

8. **Inject**
   - Resolve refs via backend
   - Print `export VAR='value'` for each secret ref
   - Ensure secret value only emitted to stdout

9. **Init / inherit**
   - `init` creates `.envrc` if missing and inserts block
   - `inherit on/off` toggles `source_up` in managed block

### Exit Criteria
- All MVP commands work on macOS
- `.envrc` never contains secret values
- `inject` yields valid export lines
- Managed block updates are safe and deterministic

---

## Phase 2 — Diagnostics & Quality of Life

**Goal:** Provide visibility, safety checks, and migration assistance.

### Scope
- `eval` command for effective environment view (masked secrets)
- `doctor` command for security diagnostics
- `.envrc` migration helper
- Shell completion scripts

### Deliverables
- `eval` prints merged env with source attribution
- `doctor` warns on insecure `.envrc` permissions and unmanaged exports
- Migration command to retrofit managed block
- Completion scripts for supported shells

### Implementation Steps
1. **Eval**
   - Compute effective view (current + parent if `source_up`)
   - Mask secrets by default
   - Show source (current vs parent)

2. **Doctor**
   - Detect world-writable `.envrc`
   - Detect unmanaged exports inside managed block
   - Report missing `eval "$(envrcctl inject)"`

3. **Migrate**
   - Parse existing `.envrc`
   - Move exports into managed block
   - Preserve external content

4. **Shell completion**
   - Generate completions for major shells
   - Document install instructions

### Exit Criteria
- `eval` and `doctor` behave predictably
- Migration reduces manual work safely
- Shell completions shipped

---

## Phase 3 — Linux Support & Extensibility

**Goal:** Enable Linux secret backend and pluggable selection.

### Scope
- SecretService backend implementation
- Backend auto-detection and configuration
- Ref schema extension for multi-backend support

### Deliverables
- Linux-compatible secret backend
- Configurable backend selection
- Expanded ref format if needed

### Implementation Steps
1. **SecretService backend**
   - Implement `get/set/delete/list` via `secret-tool` or libsecret
   - Map to ref schema

2. **Backend selection**
   - Detect OS and available backend
   - Allow explicit override via config or env var

3. **Ref schema extension**
   - Support backend prefix in refs
   - Maintain backward compatibility

### Exit Criteria
- Linux usage parity with macOS
- Pluggable backend support validated

---

## Cross-Cutting Considerations

### Project Management
- This project is managed with `uv`.
- Versioning starts at `0.0.1`.

### Security
- Avoid secrets in CLI args
- Ensure prompts use non-echo input
- TTY checks for plain output (if ever added)
- No secret values written to `.envrc`

### Testing Strategy
- Unit tests for managed block parsing/regeneration
- Integration tests for CLI flow
- Mock backend tests
- End-to-end tests for `.envrc` editing

### Documentation
- Update `README`/usage docs per phase
- Provide examples and troubleshooting

---

## Milestone Summary

- **Phase 1:** Core functionality (MVP) on macOS
- **Phase 2:** Diagnostics, eval, migration, completion
- **Phase 3:** Linux backend + extensibility