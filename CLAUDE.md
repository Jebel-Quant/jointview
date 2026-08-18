# CLAUDE.md

Guidance for Claude Code and for anyone new to this repo.

## What this is

`jointview` is a [marimo](https://marimo.io) app for comparing two price or NAV series
of a Polars DataFrame side by side: two pickers, one chart, a summary table either
side. `uvx jointview navs.parquet` starts it.

The design commitment worth knowing before changing the chart: **both series share one
y-axis.** Two scales on one plot invent a relationship that is not in the data. Where
the levels are far apart the answer is rebasing — indexing both to 100 — not a second
axis.

## Layout

Source lives in `src/jointview/`, seven modules in three layers:

| Module | Job |
| --- | --- |
| `columns.py` | **The shared vocabulary.** `PERIOD`, `series_columns`, `date_column`, `default_pair`, `aligned`. Depends on nothing else in the package. |
| `data.py` | Reading a frame off disk (`load_frame`) and generating one (`demo_frame`). |
| `plot.py` | Altair chart construction — `line_frame`, `line_chart`, and the private layer helpers. |
| `stats.py` | Summary statistics via [jQuantStats](https://github.com/jebel-quant/jquantstats). |
| `app.py` | The marimo notebook. Cells are marimo-generated; it rewrites them on save. |
| `cli.py` | The `jointview` command — builds an argv and hands it to `marimo run`. |
| `__init__.py` | The public surface, with an explicit `__all__`. |

**The dependency direction is the thing to preserve.** `plot` and `stats` are peers:
both consume what `aligned()` produces, and neither imports the other. Anything they
both need — a column name, a shaping rule — belongs in `columns.py`. `PERIOD` is the
worked example: it is the name `aligned()` writes and the name the statistics read
back, so it is a data contract, not a plotting detail.

Tests sit flat in `tests/`, one file per module. `tests/test_columns.py` and
`tests/test_stats.py` between them pin the contract above.

## Working on it

The task runner is [just](https://just.systems), not make. Recipes live in `justfile`.

```bash
just install    # venv + dependencies + pre-commit hooks
just test       # pytest with the coverage gate
just fmt        # ruff, markdownlint, bandit, actionlint, interrogate — the pre-commit set
uv run jointview   # start the app
```

No `just` on the machine, or no `uv` either? `sh scripts/just.sh <recipe>` provisions both
and then runs the recipe, so the hard prerequisites are git, curl and a POSIX shell.
`make <recipe>` also still works — see the shim note below.

Note the app line: it is **not** `just marimo`. The `marimo` and `marimo-validate` recipes
were ported from the template as they were, and both guard on `MARIMO_FOLDER`
(`docs/notebooks`), which this repo does not have — so both no-op. The app is
`src/jointview/app.py`, started by `uv run jointview` or `uvx jointview`. Repointing the
recipe at the real app would be the obvious tidy-up; it was left alone rather than folded
silently into a task-runner change.

The gates, cheapest first:

| Recipe | Checks |
| --- | --- |
| `just fmt` | pre-commit: formatting, linting, secrets, workflow validity |
| `just typecheck` | `ty` over `src` |
| `just docs-coverage` | interrogate — the bar is **100%**, every public object needs a docstring |
| `just deps` | deptry |
| `just security` | bandit |
| `just rhiza-test` | the template's own checks, from the `pytest-rhiza` plugin |
| `just test` | the suite, gated at 90% |

`just all` runs the lot. `just --list` lists every recipe.

Two bars are set higher than the defaults and are worth not sliding back on: **100%
docstring coverage** and **100% line coverage** on `src/`, against a 90% gate.

Docstring examples are executed — `pytest_rhiza.checks.test_docstrings` runs every `>>>`
as a doctest, and the README's fences are parsed too. An example that goes stale is a test
failure, so keep them true rather than illustrative.

`rhiza-test` and `test-pyproject` run the template's checks from
[pytest-rhiza](https://github.com/Jebel-Quant/pytest-rhiza), pinned to a tag, instead of
from a synced `.rhiza/tests/` folder — the same modules, installed rather than copied.
`.rhiza/tests` is excluded in `.rhiza/template.yml` because of it, so the exclusion and
these two recipes are load-bearing together: drop the recipes and `rhiza-test` measures
nothing while `test-pyproject` breaks outright. Under make these had to *shadow*
template-owned recipes from the root `Makefile`, which make announced at parse time as
"overriding commands for target"; in the justfile they are simply recipes.

### Why there is still a `Makefile`

It is a shim, and it defines no work. rhiza's reusable workflows at v1.3.3 invoke
`make <target>` **inside the caller repo**, so `make` is the CI interface whether or not
this project uses it locally: `rhiza_ci.yml` runs `test`, `typecheck`, `deps`, `fmt`,
`docs-coverage`, `security` and `license`; `rhiza_book.yml` runs `book`;
`rhiza_benchmark.yml` runs `benchmark`; `rhiza_weekly.yml` runs `test` and `semgrep`.
Every goal is forwarded to `just`, so all of that keeps working. Delete the shim once
those workflows call `just` themselves.

That list is read off tag **v1.3.3**, which is what `.rhiza/template.yml` pins — not
rhiza's `main`, which has since added `make rhiza-test` to `rhiza_ci.yml`. Worth
re-reading at the next `/rhiza:update`, since the set only grows.

Three details in it are load-bearing, and each was a bug before it was a comment:

- **`%.mk: ;`** — without it, `make -f Makefile -f something.mk` sends the *filename* to
  `just`. `rhiza_marimo.yml` reads `MARIMO_FOLDER` with exactly that shape
  (`make -f Makefile -f -`), so the guard keeps that probe answering `docs/notebooks`.
  `.DEFAULT` would avoid makefile remaking altogether and need no guards, but it ignores
  prerequisites, so a stray file named `book` or `test` would report "up to date" instead
  of running anything.
- **`-include .rhiza/.env`** — the same marimo probe parses the variable out of this file
  by including the `Makefile`. The justfile does not read `.rhiza/.env`, but the shim must.
- **`help`, `install`, `test` and `fmt` named explicitly** rather than left to the
  catch-all, because the `check-makefile-targets` pre-commit hook looks for those four.

`.rhiza/.env` therefore stays, and not only for the shim: `rhiza_ci.yml` reads
`RHIZA_CI_OS_MATRIX` from it via `make -f .rhiza/rhiza.mk -s ci-os-matrix`, which bypasses
the root `Makefile` entirely. `.rhiza/make.d/*.mk` is still on disk because the sync writes
it back, but nothing includes it any more — it is dormant, not live.

## What this repo owns, and what it does not

This is a [rhiza](https://github.com/jebel-quant/rhiza)-managed repo, synced from
template **v1.3.3**. `.rhiza/template.lock` lists every synced path; the `files:` block
is generated, so treat it as the authority rather than this table.

**Template-owned — do not edit here.** Changes are made upstream at `jebel-quant/rhiza`
and arrive via `/rhiza:update`; edits made locally are overwritten by the next sync.

- `.rhiza/` in its entirety, including `.rhiza/rhiza.mk` — except `.rhiza/template.yml`,
  which is the repo's own pointer at the template and is the one file the sync will never
  overwrite
- `.github/workflows/*` — thin stubs delegating to the reusable workflows at `@v1.3.3`
- `.pre-commit-config.yaml`, `pytest.ini`, `ruff.toml`
- `docs/mkdocs-base.yml`, `docs/index.md`

**Repo-owned — edit freely.** `src/`, `tests/`, `justfile`, `scripts/`, `Makefile`,
`pyproject.toml`, `README.md`, `mkdocs.yml`, `docs/api.md`, `.rhiza/template.yml`, and this
file.

`.rhiza/make.d/*.mk` is the one template-owned corner that is now inert: still synced,
still not to be edited here, but no longer included by anything. Do not delete it — a
deletion alone is undone by the next sync, and unlike `docs/development/` and
`.rhiza/tests/` it costs nothing to leave lying there.

**Declining a synced file takes more than deleting it** — the next sync writes it back.
`exclude:` in `.rhiza/template.yml` is what makes a refusal stick, in destination paths,
a directory entry covering everything beneath it. Two entries stand: `docs/development/`,
where the template's `MARIMO.md` and `TESTS.md` were dropped in #24, and `.rhiza/tests/`,
dropped in favour of the `pytest-rhiza` plugin. In both cases the exclusion, not the
deletion, is what keeps them gone.

`justfile` holds the work; `Makefile` forwards to it and holds none. Both are committed
rather than left to a gitignored `local.mk`, because a fresh clone needs both halves: the
`.rhiza/tests` exclusion in `.rhiza/template.yml` is committed too, and without the
`rhiza-test` recipe that exclusion silently measures nothing.

## Releasing

`/rhiza:release`, and it is **two-phase** — the split is forced by squash-merge, since
a tag must name a commit that actually lands on `main`.

1. **Phase A** — run it on a clean `main`. It bumps the version everywhere
   `[[tool.bumpversion.files]]` declares, prepends a `git-cliff` changelog section,
   and opens a release PR. **No tag is created.**
2. **Phase B** — run it again after that PR merges. It tags the merged commit and
   pushes, which triggers release CI.

Never hand-edit a version: `bump-my-version` reads `[tool.bumpversion]` in
`pyproject.toml`, and the `[project]` pattern there is deliberately anchored to that
table so a dependency sharing the number is not rewritten. A missing location is fixed
by adding a config entry.

Commits are [Conventional Commits](https://www.conventionalcommits.org) — that is what
the changelog is generated from. Pre-1.0, a breaking change is a legitimate `minor`;
`v1.0.0` is a separate decision about API stability.

One quirk to expect: between phase A and phase B, `just rhiza-test` fails
`test_latest_tag_matches_pyproject_version`, because the version has been bumped and
the tag does not exist yet. That is the release flow working as designed, not a defect.
No CI job at v1.3.3 runs `rhiza-test`, so it does not block the PR.
