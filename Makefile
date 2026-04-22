# Top-level Makefile — thin wrapper that delegates to each subproject.
#
# Each tool/server under tools/ or mcp-servers/ is self-contained with its
# own build system. This Makefile just unifies the common verbs so you (or
# an agent) don't have to remember which language a tool is written in.
#
# Usage:
#   make                       # help
#   make install               # install all subprojects
#   make test                  # test all subprojects
#   make lint                  # lint all subprojects
#   make images-install        # single subproject
#   make images-run ARGS="--help"
#
# Add a new subproject by dropping it in tools/<name>/ or mcp-servers/<name>/
# with either a pyproject.toml (Python) or a package.json (Node), then add
# its name to PY_SUBPROJECTS or TS_SUBPROJECTS below.

PY_SUBPROJECTS := images content
TS_SUBPROJECTS :=
MCP_SUBPROJECTS :=

ALL_SUBPROJECTS := $(PY_SUBPROJECTS) $(TS_SUBPROJECTS) $(MCP_SUBPROJECTS)

.PHONY: help install test lint clean $(ALL_SUBPROJECTS)

help:
	@echo "targets:"
	@echo "  install        install every subproject"
	@echo "  test           test every subproject"
	@echo "  lint           lint every subproject"
	@echo "  clean          remove build/venv/node_modules"
	@echo ""
	@echo "per-subproject (replace <name>):"
	@echo "  <name>-install  <name>-test  <name>-lint  <name>-run ARGS=..."
	@echo ""
	@echo "python subprojects: $(PY_SUBPROJECTS)"
	@echo "ts subprojects:     $(TS_SUBPROJECTS)"
	@echo "mcp servers:        $(MCP_SUBPROJECTS)"

install: $(addsuffix -install,$(ALL_SUBPROJECTS))
test:    $(addsuffix -test,$(ALL_SUBPROJECTS))
lint:    $(addsuffix -lint,$(ALL_SUBPROJECTS))
clean:   $(addsuffix -clean,$(ALL_SUBPROJECTS))

# ---- Python subprojects (uv-managed) ----
define PY_RULES
$(1)-install:
	cd tools/$(1) && uv sync
$(1)-test:
	cd tools/$(1) && uv run pytest -q || true
$(1)-lint:
	cd tools/$(1) && uv run python -m compileall -q src
$(1)-run:
	cd tools/$(1) && uv run $(1)-tool $(ARGS)
$(1)-clean:
	rm -rf tools/$(1)/.venv tools/$(1)/dist tools/$(1)/build tools/$(1)/*.egg-info
.PHONY: $(1)-install $(1)-test $(1)-lint $(1)-run $(1)-clean
endef
$(foreach p,$(PY_SUBPROJECTS),$(eval $(call PY_RULES,$(p))))

# ---- TypeScript subprojects under tools/ ----
define TS_RULES
$(1)-install:
	cd tools/$(1) && npm install
$(1)-test:
	cd tools/$(1) && npm test --silent || true
$(1)-lint:
	cd tools/$(1) && npm run lint --silent || true
$(1)-run:
	cd tools/$(1) && npm start -- $(ARGS)
$(1)-clean:
	rm -rf tools/$(1)/node_modules tools/$(1)/dist
.PHONY: $(1)-install $(1)-test $(1)-lint $(1)-run $(1)-clean
endef
$(foreach p,$(TS_SUBPROJECTS),$(eval $(call TS_RULES,$(p))))

# ---- MCP servers (TypeScript by default) ----
define MCP_RULES
$(1)-install:
	cd mcp-servers/$(1) && npm install
$(1)-test:
	cd mcp-servers/$(1) && npm test --silent || true
$(1)-lint:
	cd mcp-servers/$(1) && npm run lint --silent || true
$(1)-build:
	cd mcp-servers/$(1) && npm run build
$(1)-run:
	cd mcp-servers/$(1) && npm start -- $(ARGS)
$(1)-clean:
	rm -rf mcp-servers/$(1)/node_modules mcp-servers/$(1)/dist
.PHONY: $(1)-install $(1)-test $(1)-lint $(1)-build $(1)-run $(1)-clean
endef
$(foreach p,$(MCP_SUBPROJECTS),$(eval $(call MCP_RULES,$(p))))
