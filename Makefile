## Makefile (repo-owned)
# Keep this file small. It can be edited without breaking template sync.

LOGO_FILE=.rhiza/assets/rhiza-logo.svg

# Override template default: include mkdocstrings plugin for API docs
MKDOCS_EXTRA_PACKAGES = --with 'mkdocstrings[python]'

# Always include the Rhiza API (template-managed)
include .rhiza/rhiza.mk

# --- The rhiza checks come from pytest-rhiza, not from a synced .rhiza/tests folder ----
#
# Both recipes below shadow template-owned ones, which is why they live here rather than
# in the fragments that define them: `.rhiza/make.d/` must not be edited locally. Make
# announces each shadowing at parse time ("overriding commands for target"); those lines
# are the mechanism working, not a fault. Committed rather than left in `local.mk` so CI
# runs the checks too — gitignored, `rhiza-test` would find no directory, warn, and exit 0.
# The rationale for the whole arrangement is in CLAUDE.md and `.rhiza/template.yml`.

# Pinned to a tag rather than a branch: a gate that moves under you is not a gate.
PYTEST_RHIZA = pytest-rhiza @ git+https://github.com/Jebel-Quant/pytest-rhiza@v0.2.0

# One module per file the template used to sync. Upstream the intent is that each bundle's
# own fragment appends its line (`RHIZA_CHECKS += ...`), keeping selection at sync time;
# with the template unchanged they are spelled out here — `core` contributing the first
# two, `python-core` the next two, `tests` the last. The Rust and Go modules ship in the
# same distribution and are simply never named.
#
# `RHIZA_DOCTEST_FOLDERS` is deliberately not passed: upstream's `quality.mk` sets it from
# `DOCSTRING_FOLDERS`, which does not exist at v1.3.3, so `test_docstrings` falls back to
# `SOURCE_FOLDER` from `.rhiza/.env` — `src`, where this project's Python lives. Revisit if
# that stops being true.
RHIZA_CHECKS = \
	pytest_rhiza.checks.test_readme \
	pytest_rhiza.checks.test_release_tags \
	pytest_rhiza.checks.test_pyproject \
	pytest_rhiza.checks.test_docstrings \
	pytest_rhiza.checks.test_readme_validation

rhiza-test: install ## run the rhiza checks from pytest-rhiza
	@printf "${BLUE}[INFO] Running rhiza checks from pytest-rhiza${RESET}\n"
	@${UV_BIN} run --with "${PYTEST_RHIZA}" pytest --pyargs ${RHIZA_CHECKS}

# Unlike `rhiza-test` and `docs-coverage`, python.mk's recipe for this target names
# `.rhiza/tests/test_pyproject.py` with no existence guard, so the deleted folder breaks it
# outright rather than degrading it. Same module through the plugin; reporting flags copied
# from the template's recipe verbatim.
test-pyproject: install ## run pyproject.toml structure tests
	@${UV_BIN} run --with "${PYTEST_RHIZA}" pytest --pyargs pytest_rhiza.checks.test_pyproject \
		-v \
		--tb=long \
		--showlocals \
		-rA \
		--durations=0 \
		--no-header

# Optional: developer-local extensions (not committed). Last, so it can override the above.
-include local.mk
