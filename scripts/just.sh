#!/bin/sh
# Resolve a `just` and hand it the arguments.
#
# The one piece of bootstrap that cannot live in the justfile, for the obvious reason.
# Order of preference: a `just` already on PATH, otherwise `uvx --from rust-just just`,
# provisioning uv first when that is missing too. So the only hard prerequisites for this
# repo remain git, curl and a POSIX shell — the same set as before, minus GNU make.
#
# Used directly (`sh scripts/just.sh test`) on a fresh clone, and by the Makefile shim.
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

if command -v just >/dev/null 2>&1; then
	exec just "$@"
fi

sh "$root/scripts/uv.sh"

PATH="$root/bin:$PATH"
export PATH

exec uvx --from rust-just just "$@"
