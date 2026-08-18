## Makefile — a compatibility shim. The tasks live in `justfile`.
#
# Nothing is defined here. This file exists for one reason: rhiza's reusable workflows at
# v1.3.3 invoke `make <target>` inside the caller repo, so `make` is the CI interface
# whether or not this project uses it locally. The call sites, all upstream:
#
#   rhiza_ci.yml         test, typecheck, deps, fmt, docs-coverage, security, license
#   rhiza_book.yml       book
#   rhiza_benchmark.yml  benchmark
#   rhiza_weekly.yml     test, semgrep
#
# Read off tag v1.3.3, not rhiza's main — main has since added `make rhiza-test` to
# rhiza_ci.yml, which will arrive here with the next `/rhiza:update`.
#
# Every goal is forwarded to `just`, so all of those keep working unchanged. Delete this
# file once the reusable workflows call `just` themselves.
#
# `.rhiza/rhiza.mk` is deliberately no longer included. `.rhiza/make.d/*.mk` stays on disk
# because it is template-owned and the sync writes it back, but it is dormant — the
# fragments are not read, and the two recipes this Makefile used to *shadow* (`rhiza-test`,
# `test-pyproject`) are ordinary recipes in the justfile now, so make no longer announces
# "overriding commands for target" at parse time.
#
# One workflow bypasses this file and reads the template's make directly: rhiza_ci.yml
# runs `make -f .rhiza/rhiza.mk -s ci-os-matrix` to read RHIZA_CI_OS_MATRIX out of
# `.rhiza/.env`. That path is untouched, which is why `.rhiza/.env` must stay.

JUST := sh scripts/just.sh

# rhiza_marimo.yml parses MARIMO_FOLDER by including this file and echoing the variable,
# so the include has to survive even though the justfile no longer reads .env.
-include .rhiza/.env

.DEFAULT_GOAL := help

# Named explicitly rather than left to the catch-all, so the `check-makefile-targets`
# pre-commit hook can still find the four targets it looks for.
.PHONY: help install test fmt

help:
	@$(JUST) --list

install:
	@$(JUST) install

test:
	@$(JUST) test

fmt:
	@$(JUST) fmt

# Everything else. FORCE keeps the rule permanently out of date, since none of these
# goals name a file.
%: FORCE
	@$(JUST) $@

# Without these, make would try to remake its own makefiles *through* the catch-all above,
# forwarding a filename to just. The `%.mk` rule is the load-bearing one: rhiza_marimo.yml
# reads MARIMO_FOLDER with `make -f Makefile -f -`, and `make -f Makefile -f some.mk` fails
# outright without it. A pattern rule with a longer stem loses, so `%.mk` beats `%`.
#
# `.DEFAULT` would sidestep makefile remaking entirely and need no guards, but it ignores
# prerequisites — so a stray file named `book` or `test` at the repo root would silently
# report "up to date" instead of running the recipe. The catch-all plus FORCE does not.
Makefile: ;
%.mk: ;
.rhiza/.env: ;

.PHONY: FORCE
FORCE: ;
