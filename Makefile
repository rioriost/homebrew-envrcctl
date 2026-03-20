SHELL := /bin/sh

REPO_ROOT := $(CURDIR)
UV ?= uv
PYTHON ?= python3

DIST_DIR := $(REPO_ROOT)/dist
HELPER_SOURCE := $(REPO_ROOT)/scripts/macos/envrcctl-macos-auth.swift
HELPER_BINARY := $(REPO_ROOT)/src/envrcctl/envrcctl-macos-auth

VERSION := $(shell $(PYTHON) -c 'from pathlib import Path; import re; text = Path("pyproject.toml").read_text(encoding="utf-8"); m = re.search(r"^version\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]\s*$$", text, re.M); print(m.group(1) if m else "")')
HELPER_ARCHIVE := $(DIST_DIR)/envrcctl-macos-auth-$(VERSION)-arm64.tar.gz

.PHONY: release-artifacts sync completions dist helper helper-archive formula clean clean-dist clean-helper pre-dist post-dist

release-artifacts: sync completions dist helper-archive formula

sync:
	$(UV) sync --extra test --group dev

completions:
	$(UV) run python scripts/generate_completions.py

dist: pre-dist
	rm -rf "$(DIST_DIR)"
	$(UV) build
	$(MAKE) post-dist

helper: $(HELPER_BINARY)

$(HELPER_BINARY): $(HELPER_SOURCE) scripts/build_macos_auth_helper.sh
	sh scripts/build_macos_auth_helper.sh "$(HELPER_SOURCE)" "$(HELPER_BINARY)"

pre-dist:
	if [ -f "$(HELPER_BINARY)" ]; then mv "$(HELPER_BINARY)" "$(HELPER_BINARY).bak"; fi

post-dist:
	if [ -f "$(HELPER_BINARY).bak" ]; then mv "$(HELPER_BINARY).bak" "$(HELPER_BINARY)"; fi

helper-archive: helper
	mkdir -p "$(DIST_DIR)"
	rm -f "$(HELPER_ARCHIVE)"
	tmpdir="$$(mktemp -d)"; \
	cp "$(HELPER_BINARY)" "$$tmpdir/envrcctl-macos-auth"; \
	chmod 755 "$$tmpdir/envrcctl-macos-auth"; \
	tar -C "$$tmpdir" -czf "$(HELPER_ARCHIVE)" envrcctl-macos-auth; \
	rm -rf "$$tmpdir"

formula:
	$(PYTHON) scripts/release_artifacts.py --formula-dir ../homebrew-tap/Formula

clean: clean-dist clean-helper

clean-dist:
	rm -rf "$(DIST_DIR)"

clean-helper:
	rm -f "$(HELPER_BINARY)" "$(HELPER_BINARY).bak"
