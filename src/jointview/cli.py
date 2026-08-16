"""The `jointview` command: start marimo on the app that ships with this package."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).with_name("app.py")


def _parser() -> argparse.ArgumentParser:
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


def main(argv: list[str] | None = None) -> int:
    """Run `marimo run` (or `edit`) on the packaged notebook, and return its exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # Split on the first bare `--` before argparse sees any of it, rather than sweeping
    # up the leftovers of parse_known_args: with an optional positional in the grammar,
    # an unrecognised `--port 8080` loses its 8080 to `data`, and the mistake only
    # surfaces as marimo complaining about a flag the user never typed.
    if "--" in argv:
        cut = argv.index("--")
        argv, marimo_args = argv[:cut], argv[cut + 1 :]
    else:
        marimo_args = []

    parser = _parser()
    args = parser.parse_args(argv)

    # The notebook reads its options off mo.cli_args(), which is everything after the
    # `--` in marimo's own command line — so ours and marimo's swap sides here.
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
        return subprocess.call(command)
    except KeyboardInterrupt:
        # Ctrl-C reached the child too; it has already said its goodbyes.
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
