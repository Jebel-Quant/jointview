## Makefile (repo-owned) -- from `uvx rhiza-task shim > Makefile`, plus the bootstrap bridge below
#
# This replaces `.rhiza/rhiza.mk` and the ten fragments in `.rhiza/make.d/`: 1023 synced
# lines, at a template tag, for one pinned package version.
#
# `make` stays the front door. It is what a stranger types in an unfamiliar repository,
# what a decade of muscle memory reaches for, and what keeps the reusable workflows at
# @v1.3.3 -- which call `make test`, `make fmt`, `make book` -- working unchanged. It just
# no longer *contains* anything.
#
# RHIZA_TASK is the entire version contract. Bumping it is the migration that used to be
# `/rhiza:update` re-syncing eleven .mk files and reconciling whatever had been shadowed.
# Everything this repo used to say in make variables now lives in `[tool.rhiza-task]` in
# pyproject.toml, and everything it used to say by shadowing a target is the package's
# default. See CLAUDE.md.
RHIZA_TASK ?= rhiza-task@0.1.1

# --- Bootstrap bridge -------------------------------------------------------------------
#
# `uvx rhiza-task` presupposes uv, which is the point: the retired make layer had to curl
# `astral.sh/uv/install.sh` into `./bin` because make cannot assume it. One caller still
# needs that bootstrap. rhiza_ci.yml@v1.3.3's `pre-commit` job runs `make fmt` with no
# `astral-sh/setup-uv` step, relying on exactly this; every other job installs uv first.
#
# So: resolve uvx once, and only when it cannot be found make the install a prerequisite of
# every target. Once installed the file exists, so the recipe runs at most once. `./bin` is
# gitignored, and `PATH` is extended for that case alone so that the task process finds the
# matching `uv` beside it. Delete the whole block when the reusable workflows install uv.
#
# The recipes call `$(UVX)` by path rather than by name because make execs a single-command
# recipe itself, without a shell, and that lookup uses the PATH make started with -- so an
# exported PATH reaches the child process but not the command make is trying to run.
UVX := $(shell command -v uvx 2>/dev/null)
ifeq ($(UVX),)
UVX := $(CURDIR)/bin/uvx
UVX_BOOTSTRAP := $(UVX)
export PATH := $(CURDIR)/bin:$(PATH)
endif

$(CURDIR)/bin/uvx:
	@printf '[INFO] uvx not found -- installing uv into ./bin\n'
	@mkdir -p bin
	@curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR="$(CURDIR)/bin" UV_NO_MODIFY_PATH=1 sh

.DEFAULT_GOAL := help

help: $(UVX_BOOTSTRAP)
	@$(UVX) $(RHIZA_TASK) list

# `%:` matches any target make cannot otherwise resolve. Two caveats, both survivable: a
# typo is routed here too (the CLI's "unknown task" error is the backstop), and a task
# needing flags wants `uvx rhiza-task <task> --flag` directly. `.PHONY` cannot name unknown
# targets, so a *file* sharing a task's name would shadow it -- none do.
%: $(UVX_BOOTSTRAP)
	@$(UVX) $(RHIZA_TASK) $@

# Repo-specific one-offs live here, where they always belonged, and win over the catch-all
# because an explicit rule beats a pattern rule. This is what `local.mk` was for.
-include local.mk

# A makefile is also a target make tries to *remake* before running anything, and with a
# match-anything rule in scope that attempt is routed to the CLI -- so every invocation
# would begin with "unknown task: local.mk". An explicit rule with an empty recipe satisfies
# the remake attempt silently.
#
# `Makefile` needs one too, which the generated shim does not: make exempts an existing
# makefile from a match-anything rule only while that rule has no prerequisites, and the
# bootstrap above gives it one. Without this line `make help` tries to remake the Makefile
# by asking the CLI to build a task called "Makefile".
local.mk: ;
Makefile: ;
