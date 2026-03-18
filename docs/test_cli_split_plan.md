# `tests/test_cli.py` Split Proposal and Work Plan

## Goal

`tests/test_cli.py` has grown large enough that it now mixes multiple behavioral concerns:

- basic managed block CRUD
- secret CRUD
- `secret get`
- `inject`
- `exec`
- audit event emission
- `doctor`
- `migrate`
- `eval`
- macOS-specific auth behavior
- Linux/non-interactive behavior
- helper test doubles

The goal is to split it into smaller, topic-focused test modules without changing behavior.

## Why split now

Current issues caused by the single large file:

1. **Low navigability**
   - hard to find the test related to one command or behavior
2. **Mixed concerns**
   - functional CLI behavior and audit assertions are interleaved
3. **Fixture duplication pressure**
   - local helper classes and setup patterns are likely to drift
4. **Review cost**
   - future changes to one command force readers through unrelated tests
5. **Resume difficulty**
   - future work on one area becomes slower because the file is too broad

## Proposed target layout

### Shared test support

Create a shared helper module for common fakes and setup.

```/dev/null/tests-layout.txt#L1-12
tests/
  helpers/
    __init__.py
    cli_support.py

  test_cli_core.py
  test_cli_secret_get.py
  test_cli_inject.py
  test_cli_exec.py
  test_cli_audit.py
  test_cli_doctor.py
  test_cli_migrate.py
  test_cli_eval.py
```

## Proposed responsibility split

### `tests/helpers/cli_support.py`

Move reusable helpers here.

#### Suggested contents

- `DummyBackend`
- `_read_envrc(path)`
- maybe small setup helpers like:
  - `configure_dummy_backend(...)`
  - `init_repo_with_runner(...)`

#### Why
This removes repeated helper logic from every CLI-focused file.

---

### `tests/test_cli_core.py`

Keep small, foundational CLI behaviors here.

#### Scope

- `init`
- `set`
- `get`
- `list`
- `unset`
- `inherit`
- maybe validation-neutral happy-path envrc mutations

#### Candidate tests

- `test_cli_init_set_get_list_unset`
- `test_cli_set_adds_inject_line_when_requested`
- `test_cli_inherit_on_off`
- `test_find_nearest_envrc_dir_returns_none`
- `test_init_warns_when_world_writable`

---

### `tests/test_cli_secret_get.py`

Keep all `secret get` behavior here.

#### Scope

- interactive and non-interactive behavior
- `--plain`
- `--show`
- `--force-plain`
- clipboard path
- macOS auth path
- auth cancellation behavior
- missing secret ref behavior

#### Candidate tests

- `test_cli_secret_get_records_success_audit_event`
- `test_cli_secret_get_records_failure_audit_event`
- `test_cli_secret_get_on_macos_requires_auth_for_plain_output`
- `test_cli_secret_get_on_macos_requires_auth_for_clipboard_default`
- `test_cli_secret_get_on_macos_fails_closed_when_auth_is_cancelled`
- `test_cli_secret_get_copies_masked`
- `test_cli_secret_get_plain_interactive`
- `test_cli_secret_get_force_plain_non_interactive`
- `test_cli_secret_get_missing_ref`

---

### `tests/test_cli_inject.py`

Keep all `inject` behavior here.

#### Scope

- secret injection output
- runtime/admin filtering
- TTY behavior
- force behavior
- macOS auth behavior
- audit event recording

#### Candidate tests

- `test_cli_secret_set_inject_unset`
- `test_cli_inject_records_success_audit_event`
- `test_cli_inject_records_failure_audit_event`
- `test_cli_inject_on_macos_requires_auth`
- `test_cli_inject_on_macos_force_does_not_bypass_auth_failure`
- `test_cli_inject_requires_tty`
- `test_cli_inject_skips_admin_secrets`

---

### `tests/test_cli_exec.py`

Keep all `exec` behavior here.

#### Scope

- injection into child process
- selected keys
- runtime/admin handling
- exit code propagation
- missing command / missing selected secret
- macOS auth behavior
- audit event recording

#### Candidate tests

- `test_cli_exec_injects_secrets_into_child`
- `test_cli_exec_records_success_audit_event`
- `test_cli_exec_records_failure_audit_event`
- `test_cli_exec_on_macos_requires_auth`
- `test_cli_exec_on_macos_requires_interactive_shell`
- `test_cli_exec_on_macos_fails_closed_when_auth_is_cancelled`
- `test_cli_exec_skips_admin_secrets`
- `test_cli_exec_rejects_admin_when_selected`
- `test_cli_exec_requires_command`
- `test_cli_exec_missing_selected_secret`
- `test_cli_exec_includes_exports_and_selected_secrets`
- `test_cli_exec_propagates_exit_code`

---

### `tests/test_cli_audit.py`

Keep CLI-level audit command tests here.

#### Scope

- `audit list`
- `audit show`
- `audit verify`

#### Candidate source
Most likely move the current audit command tests from `tests/test_audit_cli.py` here only if you want all CLI command tests together.

#### Recommendation
Do **not** move them right now unless you also want to rename/reorganize `test_audit_cli.py`.
That should be a separate decision.

---

### `tests/test_cli_doctor.py`

Keep all doctor-related behavior here.

#### Scope

- symlink/group/world writable warnings
- unmanaged exports
- unmanaged secret refs
- plaintext secret warnings
- inject-line warning
- audit chain warning
- insecure audit store warning
- OK case

#### Candidate tests

- `test_cli_doctor_warns_on_symlink`
- `test_cli_doctor_warns_on_group_writable`
- `test_cli_doctor_warns_for_unmanaged_and_missing_inject`
- `test_cli_doctor_warns_for_plaintext_secrets`
- `test_doctor_warns_when_no_managed_block`
- `test_doctor_warns_for_unmanaged_secret_refs`
- `test_doctor_ok_when_no_warnings`
- `test_doctor_warns_when_audit_chain_verification_fails`
- `test_doctor_warns_when_audit_store_is_not_secure`

---

### `tests/test_cli_migrate.py`

Keep migration flows here.

#### Scope

- unmanaged export migration
- unmanaged secret ref migration
- inject-line addition during migrate

#### Candidate tests

- `test_cli_migrate_moves_unmanaged_exports`
- `test_cli_migrate_adds_inject_line_when_requested`

---

### `tests/test_cli_eval.py`

Keep `eval` behavior here.

#### Scope

- masked effective environment
- inheritance / parent envrc traversal
- stop conditions

#### Candidate tests

- `test_cli_eval_includes_parent`
- `test_eval_stops_when_no_parent_envrc`
- `test_eval_stops_when_parent_has_no_managed_block`

## Recommended decomposition strategy

Split by behavior, not by platform.

### Good split
- all `secret get` tests together, even if some are macOS-only
- all `exec` tests together, even if some are Linux-only

### Avoid
- `test_cli_macos.py`
- `test_cli_linux.py`

That kind of split usually duplicates intent and makes command behavior harder to track.

## Suggested file naming rule

Use one command/area per file where possible.

Examples:

- `test_cli_secret_get.py`
- `test_cli_exec.py`
- `test_cli_doctor.py`

This keeps grep/search simple.

## Refactoring principles

1. **Move only, don’t rewrite**
   - preserve test names first unless renaming improves clarity materially
2. **Introduce shared helpers before heavy moves**
   - avoid duplicated `DummyBackend`
3. **Keep semantic slices small**
   - one support extraction
   - then one test-file split at a time
4. **Run tests after each slice**
   - avoid giant moves without checkpoints
5. **Prefer stable imports**
   - import helpers from `tests.helpers.cli_support`

## Concrete work plan

## Phase 1: shared helper extraction

### Changes
- create `tests/helpers/cli_support.py`
- move:
  - `DummyBackend`
  - `_read_envrc`
- update `tests/test_cli.py` imports to use helper module

### Validation
- run:
  - `pytest -q tests/test_cli.py`

### Expected outcome
- no behavior change
- file shrinks slightly
- future splits become easier

---

## Phase 2: split `secret get`

### Changes
- create `tests/test_cli_secret_get.py`
- move all `secret get` tests from `tests/test_cli.py`
- keep helper imports centralized

### Validation
- run:
  - `pytest -q tests/test_cli_secret_get.py tests/test_cli.py`

### Expected outcome
- command-specific tests become easier to find
- `test_cli.py` meaningfully shrinks

---

## Phase 3: split `inject`

### Changes
- create `tests/test_cli_inject.py`
- move all `inject` tests from `tests/test_cli.py`

### Validation
- run:
  - `pytest -q tests/test_cli_inject.py tests/test_cli.py`

---

## Phase 4: split `exec`

### Changes
- create `tests/test_cli_exec.py`
- move all `exec` tests from `tests/test_cli.py`

### Validation
- run:
  - `pytest -q tests/test_cli_exec.py tests/test_cli.py`

---

## Phase 5: split `doctor`

### Changes
- create `tests/test_cli_doctor.py`
- move all doctor warning/OK tests

### Validation
- run:
  - `pytest -q tests/test_cli_doctor.py tests/test_cli.py`

---

## Phase 6: split `eval` and `migrate`

### Changes
- create:
  - `tests/test_cli_eval.py`
  - `tests/test_cli_migrate.py`
- move relevant tests

### Validation
- run:
  - `pytest -q tests/test_cli_eval.py tests/test_cli_migrate.py tests/test_cli.py`

---

## Phase 7: leave `tests/test_cli.py` as the small core file

### Target final contents
`tests/test_cli.py` should ideally contain only:

- core CRUD happy-path tests
- maybe one or two smoke-level command-integration tests
- no doctor / audit / platform-specialized command branches

### Expected size target
Rough target:
- under ~250 lines
- definitely under ~400 lines

## Suggested final state

### `tests/test_cli.py`
Core only:
- init
- set/get/list/unset
- inherit
- maybe one basic secret set/unset smoke flow

### Specialized files
Everything else moved out by command or feature area.

## Risks and mitigations

### Risk 1: duplicated fixtures during move
Mitigation:
- extract helpers first

### Risk 2: broken imports after moving
Mitigation:
- run each new file directly after move

### Risk 3: accidental behavior edits while relocating
Mitigation:
- prefer pure move commits before cleanup commits

### Risk 4: overlapping responsibilities with `test_cli_errors.py`
Mitigation:
- do not mix this split with error-file refactors yet
- keep current boundary for now
- revisit only after `test_cli.py` is reduced

## Recommended commit plan

Suggested commits:

1. `test: extract shared CLI test helpers`
2. `test: split secret get tests from test_cli`
3. `test: split inject tests from test_cli`
4. `test: split exec tests from test_cli`
5. `test: split doctor, eval, and migrate tests from test_cli`

If you want fewer commits, combine adjacent slices, but avoid doing the entire split in one commit.

## Success criteria

This split is successful when:

- `tests/test_cli.py` is substantially smaller
- command/feature tests are easy to find by filename
- no test behavior changes
- full test suite remains green
- helper setup is centralized enough to avoid repeated local fake backends

## Recommendation

Proceed incrementally.

The best first implementation step is:

1. create `tests/helpers/cli_support.py`
2. move `DummyBackend` and `_read_envrc`
3. split out `secret get`
4. split out `inject`
5. split out `exec`

That gives the highest reduction in file size with the lowest risk.