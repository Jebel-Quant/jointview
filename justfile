# justfile — the tasks for jointview (repo-owned)
#
# This replaces the make.d fragment set. `.rhiza/make.d/*.mk` is still on disk because
# it is template-owned and the sync writes it back, but nothing includes it any more:
# the root `Makefile` is a shim forwarding to this file. See CLAUDE.md.
#
# Why just: none of what used to live in those fragments was a build. There were no file
# prerequisites and no timestamp logic — every target was `.PHONY`, and `install` was
# only ever a dependency edge. What that costs under make is tab significance, `$$`
# escaping, and a hand-rolled awk `help` recipe; `just --list` and literal `$` come free.
#
# Two things came out in the wash rather than being ported:
#
#   * The `rhiza-test` / `test-pyproject` overrides. Under make these had to *shadow*
#     template-owned recipes from the root Makefile, which make announced at parse time
#     as "overriding commands for target". Here they are simply recipes.
#   * The colour-coded `[INFO]`/`[WARN]` printf ceremony. just echoes the command it is
#     about to run, which says more than a banner naming the tool does.
#
# Run it with `just <recipe>`, or `sh scripts/just.sh <recipe>` on a machine that has
# neither just nor uv — that script provisions both. `make <recipe>` also still works.

# just's default shell, stated for the record. `set windows-shell` matters: jointview's
# CI matrix includes windows-latest, where just would otherwise reach for cmd.exe. The
# GitHub Windows runners ship Git's sh.exe, which is what the make setup relied on too.
set shell := ["sh", "-cu"]
set windows-shell := ["sh", "-cu"]

# --- configuration ------------------------------------------------------------------
#
# These were variables in `.rhiza/.env` and in the fragments' `?=` defaults. They live
# here now because this file is repo-owned and there is nothing left to override from
# the outside. `.rhiza/.env` is NOT dead: `rhiza.mk` still reads RHIZA_CI_OS_MATRIX from
# it when the CI workflow calls `make -f .rhiza/rhiza.mk -s ci-os-matrix`.

source_folder := "src"
tests_folder  := "tests"
marimo_folder := "docs/notebooks"
venv          := ".venv"
book_output   := "_book"

# 100% is the bar this project actually holds on src/ (see CLAUDE.md); 90 is the gate,
# left where the template had it so a transient dip fails loudly rather than silently.
coverage_fail_under := "90"

# uv reads .python-version itself for `uv venv`/`uv run`, so this is only needed where a
# tool is provisioned outside the project environment (`uvx -p ...`).
python_version := trim(read('.python-version'))

# ty only. mypy --strict spends its findings on polars' and altair's own union-typed
# signatures — every `float(series.mean())` and every chained `.encode()` — which says
# nothing about this code. Under make this was TYPECHECKER=ty in `.rhiza/.env`, needed
# because the shared recipe defaulted to `both` and masked ty's exit code behind mypy's.
# There is no shared recipe now, so the choice is just the recipe.

# Packages exempted from the licence gate, space-separated. marimo depends on docutils,
# which is offered under a choice of licences and reports all of them as one string —
# "BSD License; GNU General Public License (GPL); Public Domain". pip-licenses matches
# --fail-on against that string with no notion of *or*, so `GPL` hits a package taken
# here under BSD.
license_ignore := "docutils"

# Where `install-uv` puts uv when the machine has none. Gitignored.
export PATH := env('PATH') + ":" + justfile_directory() / "bin"

# --- meta ---------------------------------------------------------------------------

# List the recipes (this is the default).
default:
    @just --list

# --- bootstrap ----------------------------------------------------------------------

# Ensure uv and uvx are callable, installing them into ./bin if not.
install-uv:
    @sh scripts/uv.sh

# `uv lock --check` is a hard stop rather than a silent re-resolve: `--frozen` would
# otherwise install yesterday's dependency set and say nothing.
#
# `prek install -c` — the flag is not optional. prek bakes it into the generated shim, and
# without it the commit-time gate rediscovers nested projects, meaning something different
# from `just fmt`. Skipped when an external hook manager owns core.hooksPath, because prek
# refuses to install in that case.

# venv + dependencies + pre-commit hooks.
install: install-uv
    @[ -d "{{venv}}" ] || uv venv "{{venv}}"
    uv lock --check
    uv sync --all-extras --all-groups --inexact --frozen
    @if [ -f .pre-commit-config.yaml ]; then \
        if [ -n "$(git config --get core.hooksPath 2>/dev/null || true)" ]; then \
            echo "skipping prek install: core.hooksPath is set"; \
        else \
            uvx prek install -c .pre-commit-config.yaml || echo "[warn] prek install failed"; \
        fi; \
    fi

# Remove build and test artefacts, plus local branches whose remote is gone.
clean:
    git clean -d -X -f -e '!.env' -e '!.env.*'
    rm -rf dist build *.egg-info .coverage .pytest_cache .benchmarks
    git fetch --prune
    @git branch -vv | awk '/: gone]/ && $1 != "*" && $1 != "+" {print $1}' | xargs -r git branch -D

# Shorter than the make version by the whole of its awk version comparator, which
# enforced uv >= 0.4 and git >= 2.0 — floors old enough that nothing in reach of this
# repo is below them — and a GNU-make check that is now beside the point.

# Report the local prerequisites and their versions.
doctor:
    @for tool in git uv just; do \
        if command -v "$tool" >/dev/null 2>&1; then \
            printf '  ok      %-6s %s\n' "$tool" "$($tool --version | head -1)"; \
        else \
            printf '  MISSING %-6s\n' "$tool"; \
        fi; \
    done
    @printf '  ok      python %s (from .python-version)\n' '{{python_version}}'

# --- gates --------------------------------------------------------------------------
#
# `all` names them in the order the make version did: cheapest first, so a formatting
# slip does not wait on the test suite.

# Run every gate, cheapest first.
all: fmt deps test docs-coverage security license typecheck rhiza-test

# pre-commit: formatting, linting, secrets, workflow validity.
fmt: install-uv
    uvx prek run --all-files --config .pre-commit-config.yaml

# The retry below exists for one specific failure: pytest signals a runner-internal crash
# (an xdist `worker_workerfinished` KeyError, a pytest-html report-write race) with exit
# code 3, distinct from test failures (1), interruption (2) and usage errors (4). Those
# happen during teardown, after every test has passed, and used to flip a green run red.
# Only 3 is retried, and only once. Stale `.coverage*` is cleared first so a previously
# crashed run cannot report a false 0%.

# The test suite, with the coverage gate.
test: install
    rm -rf _tests
    @mkdir -p _tests/html-coverage _tests/html-report
    @attempt=1; while :; do \
        rm -f .coverage .coverage.* 2>/dev/null || true; \
        status=0; \
        uv run --with pytest --with pytest-cov --with pytest-xdist --with pytest-html \
                --with pytest-timeout --with pytest-mock \
            pytest -n auto \
                --cov={{source_folder}} \
                --cov-report=term \
                --cov-report=html:_tests/html-coverage \
                --cov-report=json:_tests/coverage.json \
                --cov-report=xml:_tests/coverage.xml \
                --cov-fail-under={{coverage_fail_under}} \
                --html=_tests/html-report/report.html || status=$?; \
        if [ "$status" -eq 0 ]; then exit 0; fi; \
        if [ "$status" -ne 3 ] || [ "$attempt" -ge 2 ]; then exit "$status"; fi; \
        echo "[warn] pytest exited 3 (xdist teardown race, tests may all have passed); retrying"; \
        attempt=$((attempt + 1)); \
    done

# ty over src.
typecheck: install
    uv run --with ty ty check {{source_folder}}

# bandit over src. Scope lives in .bandit, not on the command line.
security: install-uv
    uvx bandit -r {{source_folder}} -ll -q --ini .bandit

# interrogate — the bar is 100%, every public object needs a docstring.
docs-coverage: install
    uv run --with interrogate interrogate -vv --fail-under 100 --ignore-init-method --ignore-magic {{source_folder}} {{tests_folder}}

# deptry over src.
deps: install-uv
    uvx -p {{python_version}} deptry {{source_folder}}

# --partial-match because the reported licence is a classifier string, not a bare name:
# without it `GPL` never equals "GNU General Public License v2 or later (GPLv2+)" and the
# gate passed with a GPL package installed.

# Licence compliance — fail on GPL, LGPL, AGPL.
license: install
    uv run --with pip-licenses pip-licenses --fail-on="GPL;LGPL;AGPL" --partial-match --ignore-packages {{license_ignore}}

# Semgrep static analysis.
semgrep: install-uv
    uvx semgrep --config .rhiza/semgrep.yml {{source_folder}}

# --- the template's own checks ------------------------------------------------------
#
# From the pytest-rhiza plugin rather than a synced `.rhiza/tests/` folder, which
# `.rhiza/template.yml` excludes. Pinned to a tag rather than a branch: a gate that moves
# under you is not a gate.
#
# One module per file the template used to sync — `core` contributing the first two,
# `python-core` the next two, `tests` the last. The Rust and Go modules ship in the same
# distribution and are simply never named.

pytest_rhiza := "pytest-rhiza @ git+https://github.com/Jebel-Quant/pytest-rhiza@v0.2.0"

rhiza_checks := "pytest_rhiza.checks.test_readme " + \
                "pytest_rhiza.checks.test_release_tags " + \
                "pytest_rhiza.checks.test_pyproject " + \
                "pytest_rhiza.checks.test_docstrings " + \
                "pytest_rhiza.checks.test_readme_validation"

# RHIZA_DOCTEST_FOLDERS is deliberately unset: test_docstrings falls back to
# SOURCE_FOLDER from `.rhiza/.env` — `src`, where this project's Python lives.

# The rhiza checks, from pytest-rhiza.
rhiza-test: install
    uv run --with "{{pytest_rhiza}}" pytest --pyargs {{rhiza_checks}}

# pyproject.toml structure tests.
test-pyproject: install
    uv run --with "{{pytest_rhiza}}" pytest --pyargs pytest_rhiza.checks.test_pyproject \
        -v --tb=long --showlocals -rA --durations=0 --no-header

# --- optional test extras ------------------------------------------------------------
#
# jointview has no benchmarks/, stress/ or property-marked tests. These stay because CI
# names them — rhiza_benchmark.yml runs `benchmark`, and `book` collects all four into
# docs/reports — and because a missing recipe is an error where a skipped one is not.

# Performance benchmarks (pytest-benchmark).
benchmark: install
    @if [ ! -d "{{tests_folder}}/benchmarks" ]; then echo "no {{tests_folder}}/benchmarks, skipping"; exit 0; fi; \
    mkdir -p _tests/benchmarks; \
    uv run --with pytest --with pytest-benchmark==5.2.3 --with pygal==3.1.0 \
        pytest "{{tests_folder}}/benchmarks/" \
            --benchmark-only \
            --benchmark-histogram=_tests/benchmarks/histogram \
            --benchmark-json=_tests/benchmarks/results.json

# Property-based tests (Hypothesis). Exit 5 — nothing collected — is not a failure.
hypothesis-test: install
    @mkdir -p _tests/hypothesis; \
    status=0; \
    PYTEST_HTML_TITLE="Hypothesis tests" uv run --with pytest --with hypothesis --with pytest-html \
        pytest -v -m "hypothesis or property" \
            --hypothesis-show-statistics \
            --hypothesis-seed=0 \
            --tb=short \
            --html=_tests/hypothesis/report.html || status=$?; \
    if [ "$status" -eq 5 ]; then echo "no hypothesis/property tests collected, skipping"; exit 0; fi; \
    exit "$status"

# Stress and load tests.
stress: install
    @if [ ! -d "{{tests_folder}}/stress" ]; then echo "no {{tests_folder}}/stress, skipping"; exit 0; fi; \
    mkdir -p _tests/stress; \
    uv run --with pytest --with pytest-html \
        pytest -v -m stress --tb=short --html=_tests/stress/report.html

# Mutation testing (mutmut). Reports even when mutants survive; exits with mutmut's status.
mutation: install
    @mkdir -p _tests/mutation; \
    run_status=0; \
    uv run --with mutmut mutmut run --paths-to-mutate="{{source_folder}}" --tests-dir="{{tests_folder}}" || run_status=$?; \
    uv run --with mutmut mutmut html; \
    rm -rf _tests/mutation/html; \
    mv html _tests/mutation/html; \
    uv run --with mutmut mutmut results; \
    exit "$run_status"

# --- book ---------------------------------------------------------------------------

# `--with mkdocstrings[python]` is this repo's addition — docs/api.md needs it. Under
# make it was MKDOCS_EXTRA_PACKAGES, set in the root Makefile to override the fragment's
# empty default.
zensical := "'zensical>=0.0.36'"

[private]
_book-notebooks:
    @if [ ! -d "{{marimo_folder}}" ]; then echo "no {{marimo_folder}}, skipping notebook export"; exit 0; fi; \
    for nb in {{marimo_folder}}/*.py; do \
        name=$(basename "$nb" .py); \
        echo "exporting $nb -> docs/notebooks/$name.html"; \
        ( cd "$(dirname "$nb")" && uv run --with marimo marimo export html --sandbox "$(basename "$nb")" \
            -o "{{justfile_directory()}}/docs/notebooks/$name.html" ); \
    done

# Compile the companion book via zensical.
book: test benchmark stress hypothesis-test _book-notebooks
    @if [ -d _tests ] && [ -n "$(ls -A _tests 2>/dev/null)" ]; then \
        mkdir -p docs/reports && cp -r _tests/. docs/reports/; \
    else \
        echo "no _tests to copy into docs/reports"; \
    fi
    rm -rf "{{book_output}}"
    uvx --with 'mkdocstrings[python]' {{zensical}} build -f mkdocs.yml
    @mkdir -p "{{book_output}}" && touch "{{book_output}}/.nojekyll"
    @if [ -f _tests/coverage.xml ]; then \
        uvx "genbadge[coverage]" coverage -i _tests/coverage.xml -o "{{book_output}}/coverage-badge.svg"; \
    fi

# Build the book and serve it at http://localhost:8000.
serve: book
    cd "{{book_output}}" && uv run python -m http.server 8000

# --- marimo --------------------------------------------------------------------------
#
# Both of these guard on {{marimo_folder}}, which does not exist in this repo — the app
# itself is src/jointview/app.py, started by `uvx jointview` or `uv run jointview`. Ported
# as they were rather than repointed; see the note in CLAUDE.md.

# Start the marimo server over the notebook folder.
marimo: install
    @if [ ! -d "{{marimo_folder}}" ]; then echo "no {{marimo_folder}}, nothing to start"; exit 0; fi; \
    uv run --no-project --with marimo --directory "{{marimo_folder}}" marimo edit --no-token --headless

# Check that every marimo notebook runs.
marimo-validate: install
    @if [ ! -d "{{marimo_folder}}" ]; then echo "no {{marimo_folder}}, skipping validation"; exit 0; fi; \
    failed=0; \
    for nb in {{marimo_folder}}/*.py; do \
        stem=$(basename "$nb" .py); \
        mkdir -p "results/$stem"; \
        if NOTEBOOK_OUTPUT_FOLDER="results/$stem" uv run "$nb" >/dev/null 2>&1; then \
            echo "ok      $stem"; \
        else \
            echo "FAILED  $stem"; \
            failed=$((failed + 1)); \
        fi; \
    done; \
    [ "$failed" -eq 0 ] || { echo "$failed notebook(s) failed"; exit 1; }

# --- housekeeping and GitHub helpers -------------------------------------------------

# Report every TODO, FIXME and HACK comment.
todos:
    @git grep -nE '(TODO|FIXME|HACK):' -- ':!justfile' || echo "none found"

[private]
_gh:
    @command -v gh >/dev/null 2>&1 || { \
        echo "gh not found — https://github.com/cli/cli#installation"; exit 1; }

# The gh --template arguments are Go templates, so they are full of `{{` — which is also
# just's interpolation opener. They live in single-quoted variables because a *raw string*
# is the one place just does not scan for `{{`, and the substituted text is not re-scanned.
# Escaping them inline does not work: `{{{{` correctly yields `{{`, but there is no
# matching escape for `}}`, so `}}}}` comes out as four braces.

prs_template := '{{tablerow (printf "NUM" | color "bold") (printf "TITLE" | color "bold") (printf "AUTHOR" | color "bold") (printf "BRANCH" | color "bold") (printf "UPDATED" | color "bold")}}{{range .}}{{tablerow (printf "#%v" .number | color "green") .title (.author.login | color "cyan") (.headRefName | color "yellow") (timeago .updatedAt | color "white")}}{{end}}'

issues_template := '{{tablerow (printf "NUM" | color "bold") (printf "TITLE" | color "bold") (printf "AUTHOR" | color "bold") (printf "LABELS" | color "bold") (printf "UPDATED" | color "bold")}}{{range .}}{{tablerow (printf "#%v" .number | color "green") .title (.author.login | color "cyan") (pluck "name" .labels | join ", " | color "yellow") (timeago .updatedAt | color "white")}}{{end}}'

runs_template := '{{tablerow (printf "STATUS" | color "bold") (printf "NAME" | color "bold") (printf "BRANCH" | color "bold") (printf "EVENT" | color "bold") (printf "TIME" | color "bold")}}{{range .}}{{tablerow (printf "%s" .conclusion | color "red") .name (.headBranch | color "cyan") (.event | color "yellow") (timeago .createdAt | color "white")}}{{end}}'

# List open pull requests.
view-prs: _gh
    @gh pr list --json number,title,author,headRefName,updatedAt --template '{{prs_template}}'

# List open issues.
view-issues: _gh
    @gh issue list --json number,title,author,labels,updatedAt --template '{{issues_template}}'

# List recent failing workflow runs.
failed-workflows: _gh
    @gh run list --limit 10 --status failure --json conclusion,name,headBranch,event,createdAt --template '{{runs_template}}'

# Show the GitHub auth status.
whoami: _gh
    @gh auth status --hostname github.com

# Show recent runs of the release workflow.
workflow-status: _gh
    @wf=$(gh workflow list --json name,id --jq '.[] | select(.name | test("release";"i")) | .name' 2>/dev/null | head -1); \
    if [ -z "$wf" ]; then echo "no release workflow in this repository"; exit 0; fi; \
    echo "workflow: $wf"; \
    gh run list --workflow "$wf" --limit 5 --json status,conclusion,headBranch,event,createdAt,displayTitle

# Show the latest GitHub release.
latest-release: _gh
    @gh release view --json tagName,name,publishedAt,url,isDraft,isPrerelease,author 2>/dev/null \
        || echo "no releases in this repository"
