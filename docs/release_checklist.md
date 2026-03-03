# Release Checklist — envrcctl

## Pre-release
- [ ] Update version in `pyproject.toml` and any release notes.
- [ ] Ensure dependencies are up to date (`uv.lock` refreshed if needed).
- [ ] Confirm README examples are accurate.

## Security Review
- [ ] Review `docs/threat_model.md` for accuracy.
- [ ] Run `envrcctl doctor` on a representative repo to confirm warnings are helpful.
- [ ] Verify that no secrets are written to `.envrc`.
- [ ] Ensure secret ref validation rules are unchanged or documented.

## Verification
- [ ] Run `./.zed/scripts/verify` on this branch.
- [ ] Run `./.zed/scripts/verify-release` for coverage and security linting.
- [ ] Confirm no new warnings in tests related to secret handling.

## Packaging
- [ ] Build sdist/wheel with `hatchling` (or release toolchain).
- [ ] Install from the built artifact and run a smoke test:
  - `envrcctl init`
  - `envrcctl set FOO bar`
  - `envrcctl secret set TOKEN --account test --stdin`

## Documentation
- [ ] Update `docs/impl_tickets.json` status for completed work.
- [ ] Review `README.md` and `README.jp.md` for any required changes.

## Release Steps
- [ ] Tag the release in git (annotated tag).
- [ ] Publish artifacts to the chosen distribution channel.
- [ ] Verify Homebrew formula (if applicable) references correct URL/SHA256.

## Post-release
- [ ] Monitor issue tracker for regressions.
- [ ] Archive release notes and test logs.