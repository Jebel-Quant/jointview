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
uv run marimo edit src/jointview/app.py   # the app, in the editor
```

`make marimo` is not that command: it opens `MARIMO_FOLDER` (`docs/notebooks`), which this
repo does not have, so it skips. The notebook here is the package's own `app.py`.

The gates, cheapest first:

| Target | Checks |
| --- | --- |
| `make fmt` | pre-commit: formatting, linting, secrets, workflow validity |
| `make typecheck` | `ty` over `src` |
| `make docs-coverage` | interrogate — the bar is **100%**, every public object needs a docstring |
| `make deps` | deptry over `src` |
| `make security` | bandit |
| `make rhiza-test` | the template's own checks, from the `pytest-rhiza` plugin |
| `make test` | the suite, gated at `COVERAGE_FAIL_UNDER` |

`make all` runs the lot. `make help` lists every target.

Two bars are set higher than the defaults and are worth not sliding back on: **100%
docstring coverage** and **100% line coverage** on `src/`, against a 90% gate.

Docstring examples are executed — `pytest_rhiza.checks.test_docstrings` runs every `>>>`
as a doctest, and the README's fences are parsed too. An example that goes stale is a test
failure, so keep them true rather than illustrative.

**None of that is make any more.** The targets are tasks in
[rhiza-task](https://github.com/jebel-quant/rhiza-task), pinned in `Makefile` to one
version on PyPI; `make <anything>` is a catch-all rule forwarding to `uvx rhiza-task
<anything>`. `.rhiza/rhiza.mk` and the ten fragments in `.rhiza/make.d/` — 1023 synced
lines — are gone, and with them the two check overrides this file used to describe: the
`rhiza-test` and `test-pyproject` tasks call
[pytest-rhiza](https://github.com/Jebel-Quant/pytest-rhiza) themselves, so there is
nothing left to shadow.
`uvx rhiza-task list` is the same listing `make help` prints, and `uvx rhiza-task <task>
--flag` is how you reach a flag the catch-all cannot pass, `--strict` above all: it turns a
gate that found nothing to measure from a yellow line into a red one.

Everything the repo still says for itself is said in one place: `[tool.rhiza-task]` in
`pyproject.toml`. It pins pytest-rhiza to an exact PyPI version rather than the package's
default git tag, adds `mkdocstrings[python]` to the book build, and holds the three-OS CI
matrix.

**`.rhiza/.env` is gone too, and this is where its last setting went.** The file carried
four variables and three of them — `SOURCE_FOLDER=src`, `MARIMO_FOLDER=docs/notebooks`,
`TYPECHECKER=ty` — had become verbatim restatements of `rhiza_task.config.Config`'s
dataclass defaults, `ty` included: the reason for choosing it (`both` masks ty's exit code
behind mypy's, and mypy `--strict` spends its findings on polars' and altair's own
union-typed signatures) is now upstream's default rather than this repo's override. Only
`RHIZA_CI_OS_MATRIX` said something the defaults do not, since the default is
`["ubuntu-latest"]` alone, so it moved to `ci-os-matrix` in `[tool.rhiza-task]` — a layer
*above* `.env` in the five-layer resolution order, so nothing about precedence changed.
`.rhiza/.gitignore` went with it: its single line was `!.env`, un-ignoring the file against
the root `.gitignore`, and with no `.env` there is nothing to un-ignore.

## What this repo owns, and what it does not

This is a [rhiza](https://github.com/jebel-quant/rhiza)-managed repo, synced from
template **v1.4.2**. `.rhiza/template.lock` lists every synced path; the `files:` block
is generated, so treat it as the authority rather than this table.

**Template-owned — do not edit here.** Changes are made upstream at `jebel-quant/rhiza`
and arrive via `/rhiza:update`; edits made locally are overwritten by the next sync.

- `.rhiza/` in its entirety — except `.rhiza/template.yml`, the repo's own pointer at the
  template and the one file the sync will never overwrite
- `.github/workflows/*` — thin stubs delegating to the reusable workflows at `@v1.4.2`,
  all of them: `rhiza_ci.yml` had been pinned ahead at `@v1.3.4` for the
  `generate-matrix` reason below, and v1.4.2 levelled it with the rest. A `/rhiza:update`
  moves the refs and `.rhiza/template.lock` together.
  **`rhiza_release.yml` is the exception and is now repo-owned**: it is synced whole
  rather than delegating, because the PyPI publish has to run under this repository's
  identity for Trusted Publishing. Its conda and devcontainer jobs were removed — no
  `.devcontainer` here, no feedstock waiting on a grayskull recipe — and an `exclude:`
  entry is what keeps them removed. The price is that upstream fixes to the release
  pipeline no longer arrive; check the template's copy by hand when one lands.
- `.pre-commit-config.yaml`, `pytest.ini`, `ruff.toml`
- `docs/mkdocs-base.yml`, `docs/index.md`

**Repo-owned — edit freely.** `src/`, `tests/`, `pyproject.toml`, `README.md`,
`mkdocs.yml`, `docs/api.md`, `.rhiza/template.yml`,
`.github/workflows/rhiza_release.yml`, and this file.

**Declining a synced file takes more than deleting it** — the next sync writes it back.
`exclude:` in `.rhiza/template.yml` is what makes a refusal stick, in destination paths,
a directory entry covering everything beneath it. Eleven entries stand: `docs/development/`,
where the template's `MARIMO.md` and `TESTS.md` were dropped in #24; `.rhiza/tests/`,
dropped in favour of the `pytest-rhiza` plugin; `.rhiza/make.d/` with `.rhiza/rhiza.mk`,
dropped in favour of `rhiza-task`; `.rhiza/.env` with `.rhiza/.gitignore`, dropped once
`[tool.rhiza-task]` held the only setting either of them still carried; `.github/CONFIG.md`,
a walkthrough for configuring `PAT_TOKEN` and the release secrets in the GitHub UI, which
belongs to whoever set the repo up rather than to anyone reading the tree — and whose
central subject, a stored PyPI credential, does not apply to a repo publishing by Trusted
Publishing; `.github/workflows/rhiza_fuzzing.yml` with `.github/workflows/rhiza_mutation.yml`,
the two opt-in workflows v1.4.2 added, both off unless a repository variable turns them on and
neither turned on here — there is no parser and no untrusted input in a marimo app over two
Polars columns for a fuzzer to reach, and the assertion-strength question mutation testing
asks is one that 100% line coverage over seven small modules already answers cheaply. Their
gates sit in different places, which is why declining both is one decision rather than two:
mutation's `if:` is in the stub, so the job never starts, while fuzzing's is inside the
reusable workflow, so the job does start on every pull request in order to skip. Then
`.github/ISSUE_TEMPLATE/`, the two issue forms — 98 lines of required fields, for a
repository whose issues are opened by the person who wrote the code, where the friction
lands entirely on the one contributor a form's structure was never meant to discipline.
Issues stay enabled and free-form. And `.github/workflows/rhiza_release.yml`, which is kept
rather than dropped — the exclusion protects a local edit to a synced file instead of
refusing the file. In every other case the exclusion, not the deletion, is what makes the
refusal stick — which is why the make entries stay after the files themselves are gone from
the tree.

`.github/DISCUSSION_TEMPLATE/` is the one that survived the same question, and only just:
its three forms are inert here because Discussions is switched off on the repository, so
they cost nothing and are already configured if it is ever switched on.

**One bridge is left, and it is temporary.** The reusable workflows call `make`, which is
why the shim exists at all, but `rhiza_ci.yml`'s `pre-commit` job runs `make fmt` with no
`astral-sh/setup-uv` step, because the retired make layer bootstrapped uv itself. `Makefile`
keeps that fallback: when `uvx` is not on `PATH` it installs uv into the gitignored `./bin`,
which is also prepended to `PATH`. Every other job sets uv up first and never triggers it,
and the bridge goes when that job does.

**There were two.** `generate-matrix` ran `make -f .rhiza/rhiza.mk -s ci-os-matrix`, which
made a *path* part of the reusable contract: this repo had to keep four repo-owned lines at
`.rhiza/rhiza.mk` whose only caller was that step. Since `@v1.3.4` the step installs uv and
runs `uvx rhiza-task ci-os-matrix` (jebel-quant/rhiza#1546), so the file is gone — deleted
here, and still excluded in `.rhiza/template.yml` so the sync cannot write the template's
original back. It asks the CLI for the matrix rather than reading a path, which is also what
let `.rhiza/.env` go afterwards: the setting stayed put and only its file changed, from
`RHIZA_CI_OS_MATRIX` there to `ci-os-matrix` in `[tool.rhiza-task]`. That step is also why
the pin is at `rhiza-task@0.1.2` or later: it exports an
intentionally *empty* `RHIZA_CI_OS_MATRIX` for every repo that is not the template's own,
and 0.1.1 resolved an empty string to a value and answered `[]` — which GitHub expands to
zero jobs rather than failing (Jebel-Quant/rhiza-task#4).

`Makefile` otherwise holds one variable — the `rhiza-task` version, which is the entire
version contract — and optionally includes a gitignored `local.mk` last; a repo-specific
target belongs in either, and an explicit rule in both beats the catch-all.

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
