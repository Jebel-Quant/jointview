"""`python -m jointview`, the same thing the console script does."""

from jointview.cli import main

# Guarded, because this module is importable as `jointview.__main__` and anything that
# walks the package — doctest collection, pydoc, autodoc — would otherwise launch a
# marimo server and block. Under `python -m jointview` the name is `__main__`, so the
# entry point itself is unaffected.
if __name__ == "__main__":
    raise SystemExit(main())
