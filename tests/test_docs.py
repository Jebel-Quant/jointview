"""The Python examples on the documentation pages this repo owns actually run.

The template already validates `README.md` — `.rhiza/tests/test_readme_validation.py`
executes its fences — and the doctest gate covers every `>>>` in `src/`. Nothing
reached `docs/`, which is how the API reference came to ship a call that raised
`TypeError` from the day the page was written: it rendered perfectly, and the same
example spelled correctly in the README kept passing.

Scope is the pages **this repo owns**, read from `.rhiza/template.lock` rather than
listed here. `docs/index.md` and `docs/development/*.md` are synced from the template,
so their examples are upstream's to fix and their illustrative snippets — calls to a
`perform_operation()` that exists nowhere — are not defects to be reported here.

A fence that is meant to be read rather than run opts out the same way it does in the
README, by flagging the opening line:

    ```python +RHIZA_SKIP
"""

import re
import subprocess  # nosec B404  # running the docs is the point of this module
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / ".rhiza/template.lock"

# Same shape as the template's README validator: capture the flags after the language
# so a fence can opt out, and the body separately.
CODE_BLOCK = re.compile(r"```python([^\n]*)\n(.*?)```", re.DOTALL)
SKIP_FLAG = "+RHIZA_SKIP"


def _template_owned() -> set[str]:
    """The repo-relative paths listed under `files:` in the template lock."""
    owned: set[str] = set()
    in_files = False
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if line.startswith("files:"):
            in_files = True
        elif in_files:
            # The block ends at the first line that is not a list entry.
            if not line.startswith("- "):
                break
            owned.add(line.removeprefix("- ").strip())
    return owned


def _our_docs() -> list[Path]:
    """Every markdown page under docs/ that the template does not own."""
    owned = _template_owned()
    return sorted(p for p in (ROOT / "docs").rglob("*.md") if str(p.relative_to(ROOT)) not in owned)


def _runnable(page: Path) -> list[str]:
    """The python fences on ``page`` that have not opted out."""
    return [code for flags, code in CODE_BLOCK.findall(page.read_text(encoding="utf-8")) if SKIP_FLAG not in flags]


def test_the_lock_is_readable_and_names_the_synced_docs():
    """The scoping above is only meaningful if the lock actually parsed."""
    owned = _template_owned()
    assert "docs/index.md" in owned
    assert "docs/api.md" not in owned


@pytest.mark.parametrize("page", _our_docs(), ids=lambda p: p.name)
def test_the_examples_on_our_docs_pages_run(page):
    """Every non-skipped python fence executes without raising.

    Fences on one page are concatenated and run as a single script, so a later one may
    build on the names an earlier one bound — which is how a page reads.
    """
    code = "\n".join(_runnable(page))
    if not code.strip():
        pytest.skip(f"no runnable python fences in {page.name}")

    # Trust boundary: this is documentation committed to this repo and reviewed in PRs,
    # executed on the interpreter running the tests so it sees the installed package.
    result = subprocess.run(  # nosec
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, f"{page.relative_to(ROOT)} raised:\n{result.stderr}"
