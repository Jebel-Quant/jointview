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

```bash
make install    # venv + dependencies + pre-commit hooks
make test       # pytest with the coverage gate
make fmt        # ruff, markdownlint, bandit, actionlint, interrogate — the pre-commit set
make marimo     # start the app
```

The gates, cheapest first:

| Target | Checks |
| --- | --- |
| `make fmt` | pre-commit: formatting, linting, secrets, workflow validity |
| `make typecheck` | `ty` over `src` |
| `make docs-coverage` | interrogate — the bar is **100%**, every public object needs a docstring |
| `make deps` | deptry (`make deptry` is the deprecated alias) |
| `make security` | bandit |
| `make rhiza-test` | the template's own checks, from the `pytest-rhiza` plugin |
| `make test` | the suite, gated at `COVERAGE_FAIL_UNDER` |

`make all` runs the lot. `make help` lists every target.

Two bars are set higher than the defaults and are worth not sliding back on: **100%
docstring coverage** and **100% line coverage** on `src/`, against a 90% gate.

Docstring examples are executed — `pytest_rhiza.checks.test_docstrings` runs every `>>>`
as a doctest, and the README's fences are parsed too. An example that goes stale is a test
failure, so keep them true rather than illustrative.

**`make rhiza-test` and `make test-pyproject` are overridden in the `Makefile`.** They run
the template's checks from [pytest-rhiza](https://github.com/Jebel-Quant/pytest-rhiza),
pinned to a tag, instead of from a synced `.rhiza/tests/` folder — the same seven modules,
installed rather than copied. `.rhiza/tests` is excluded in `.rhiza/template.yml` because
of it, and the two are load-bearing together: without the override `rhiza-test` finds no
directory, prints a warning and **exits 0**, so `make all` would go green measuring
nothing. Committed rather than left in a gitignored `local.mk` for exactly that reason —
CI needs the replacement too. Both revert once the template ships the plugin wiring.

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

**Repo-owned — edit freely.** `src/`, `tests/`, `pyproject.toml`, `README.md`,
`mkdocs.yml`, `docs/api.md`, `.rhiza/template.yml`, and this file.

**Declining a synced file takes more than deleting it** — the next sync writes it back.
`exclude:` in `.rhiza/template.yml` is what makes a refusal stick, in destination paths,
a directory entry covering everything beneath it. Two entries stand: `docs/development/`,
where the template's `MARIMO.md` and `TESTS.md` were dropped in #24, and `.rhiza/tests/`,
dropped in favour of the `pytest-rhiza` plugin. In both cases the exclusion, not the
deletion, is what keeps them gone.

`Makefile` sets two variables, includes `.rhiza/rhiza.mk`, and optionally includes a
gitignored `local.mk` last. It was a four-line shim until the two check overrides above
moved in; anything that must survive a clone belongs there, and genuinely local targets in
`local.mk`, which is included after and so still wins.

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

One quirk to expect: between phase A and phase B, `make rhiza-test` fails
`test_latest_tag_matches_pyproject_version`, because the version has been bumped and
the tag does not exist yet. That is the release flow working as designed, not a defect.
No CI job runs `rhiza-test`, so it does not block the PR.
