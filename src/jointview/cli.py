"""The `jointview` command: start marimo on the app that ships with this package."""

from __future__ import annotations

import argparse
import subprocess  # nosec B404  # launching marimo is what this module is for
import sys
from pathlib import Path

APP = Path(__file__).with_name("app.py")


def _parser() -> argparse.ArgumentParser:
    """The app's own arguments — everything marimo's command line does not own."""
    parser = argparse.ArgumentParser(
        prog="jointview",
        description="Compare two price or NAV series of a table, side by side.",
        epilog=(
            "Arguments after a bare -- go to marimo untouched, for the server itself: "
            "jointview navs.parquet -- --port 8080 --headless"
        ),
    )
    parser.add_argument(
        "data",
        nargs="?",
        help=(
            "table to read: .parquet, .csv, .tsv, .json, .ndjson, .arrow, .ipc or "
            ".feather. Omitted, you get the generated demo frame."
        ),
    )
    # The notebook's own option is spelled --data, and that is what this took back when
    # it was `marimo run app.py -- --data ...`. Kept as a hidden alias of the
    # positional, so the old line still runs.
    parser.add_argument("--data", dest="data_flag", help=argparse.SUPPRESS)
    parser.add_argument(
        "--height",
        type=int,
        help="plot height in pixels (default 700, which suits a laptop window).",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="open the notebook itself instead of running it.",
    )
    return parser


def _split(argv: list[str]) -> tuple[list[str], list[str]]:
    """Cut ``argv`` at the first bare ``--`` into our arguments and marimo's.

    Done before argparse sees any of it, rather than sweeping up the leftovers of
    parse_known_args: with an optional positional in the grammar, an unrecognised
    `--port 8080` loses its 8080 to `data`, and the mistake only surfaces as marimo
    complaining about a flag the user never typed.

    >>> _split(["navs.parquet", "--", "--port", "8080"])
    (['navs.parquet'], ['--port', '8080'])
    >>> _split(["navs.parquet"])
    (['navs.parquet'], [])
    """
    if "--" not in argv:
        return argv, []
    cut = argv.index("--")
    return argv[:cut], argv[cut + 1 :]


def _app_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    """The notebook's own options, as the command line it reads off ``mo.cli_args()``.

    That is everything after the `--` in marimo's command line — so ours and marimo's
    swap sides here.
    """
    app_args: list[str] = []
    data = args.data_flag or args.data
    if data:
        # Absolute, because the path was typed relative to the shell and the notebook
        # it is bound for lives in a wheel somewhere under the uv cache. Checked here
        # too: a missing file should be a line from the shell, not a traceback in a
        # cell of a notebook that has already opened a browser tab.
        file = Path(data).expanduser().resolve()
        if not file.exists():
            parser.error(f"no such file: {data}")
        app_args += ["--data", str(file)]
    if args.height:
        app_args += ["--height", str(args.height)]
    return app_args


def main(argv: list[str] | None = None) -> int:
    """Run `marimo run` (or `edit`) on the packaged notebook, and return its exit code."""
    ours, marimo_args = _split(list(sys.argv[1:] if argv is None else argv))

    parser = _parser()
    args = parser.parse_args(ours)
    app_args = _app_args(args, parser)

    # `python -m marimo`, not a bare `marimo`: under uvx the two need not be the same
    # interpreter, and only this one is sure to have jointview importable — which the
    # notebook needs on its first cell.
    command = [
        sys.executable,
        "-m",
        "marimo",
        "edit" if args.edit else "run",
        # In front of the notebook path, where `marimo run [OPTIONS] NAME` wants them;
        # after it they would be read as arguments to the notebook.
        *marimo_args,
        str(APP),
    ]
    if app_args:
        command += ["--", *app_args]

    try:
        # No shell, and argv is a list, so nothing here is word-split or glob-expanded:
        # the executable is this interpreter, the notebook path is the installed
        # wheel's, and the rest are the user's own arguments on their own machine —
        # the same ones they would have typed after `marimo run`.
        return subprocess.call(command)  # noqa: S603 # nosec B603
    except KeyboardInterrupt:
        # Ctrl-C reached the child too; it has already said its goodbyes.
        return 130
