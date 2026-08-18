#!/bin/sh
# Ensure `uv` and `uvx` are callable, installing them into ./bin when they are not.
#
# Committed, and not folded into the justfile, because rhiza's reusable CI does not
# provision uv for every job: the "Pre-commit hooks" job in rhiza_ci.yml@v1.3.3 has no
# setup-uv step and relies on the project bootstrapping its own uv on the way to `fmt`.
# Silent on the happy path.
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

if command -v uv >/dev/null 2>&1 && command -v uvx >/dev/null 2>&1; then
	exit 0
fi

if [ -x "$root/bin/uv" ] && [ -x "$root/bin/uvx" ]; then
	exit 0
fi

echo "[info] installing uv into $root/bin"
mkdir -p "$root/bin"
curl -LsSf https://astral.sh/uv/install.sh \
	| UV_INSTALL_DIR="$root/bin" UV_NO_MODIFY_PATH=1 sh >/dev/null
