## .rhiza/rhiza.mk -- repo-owned bridge, NOT the template's file of that name
#
# The 200-line synced original and the ten fragments in `.rhiza/make.d/` are gone: the
# tasks come from `rhiza-task` on PyPI now, and `Makefile` forwards to it. Both paths are
# excluded in `.rhiza/template.yml`, which is what keeps the sync from writing them back
# -- and, for this path, from overwriting the four lines below.
#
# One caller still names it. rhiza_ci.yml@v1.3.3's `generate-matrix` job runs
#
#   make -f .rhiza/rhiza.mk -s ci-os-matrix
#
# in a job that installs no uv, so the answer has to come from make rather than from
# `uvx rhiza-task ci-os-matrix`. Both readers take it from `.rhiza/.env`, which stays the
# one source of truth. Delete this file once the reusable workflows read the matrix from
# the CLI.
-include .rhiza/.env

.PHONY: ci-os-matrix
ci-os-matrix: ## Emit GitHub CI OSes (RHIZA_CI_OS_MATRIX as JSON array, default ["ubuntu-latest"])
	@$(info $(or $(RHIZA_CI_OS_MATRIX),["ubuntu-latest"]))
