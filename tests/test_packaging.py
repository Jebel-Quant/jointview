"""What the built wheel has to carry, which the source tree cannot vouch for.

The suite otherwise imports `jointview` from `src/` through the editable install, so
every test here passes on files that may never reach a wheel. `py.typed` is the case
where that gap matters: the marker is what PEP 561 requires before any consumer's type
checker will read the annotations in the modules beside it, and a marker present in
`src/` but absent from the artifact is indistinguishable from having none at all.

Nothing in the editable install's own metadata can answer this. `uv` installs the
project as a `.pth` file, so its RECORD lists the `dist-info` and the path entry and
nothing under `jointview/` — the package files it claims to install are not enumerated
anywhere to check against.

So the wheel is built and opened. It is the artifact the question is about, and at the
time of writing a warm build takes about 15ms.

`tests/test_rhiza_packaging.py` is next door and asks a different question — whether the
declared version matches the installed one. It is also template-owned, synced from
`jebel-quant/rhiza` and listed in `.rhiza/template.lock`, which is why this lives in its
own file rather than as a case added to that one: the next sync would overwrite it.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

# tests/ sits at the project root, so the parent of this file's directory is the root.
_ROOT = Path(__file__).absolute().parent.parent


@pytest.fixture(scope="session")
def wheel(tmp_path_factory) -> Path:
    """The project built as a wheel, out of tree.

    Session-scoped for the same reason `conftest.resources` is: the bytes are the same
    for every test that asks, and building once is the whole saving.
    """
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("no uv on PATH to build a wheel with")

    out = tmp_path_factory.mktemp("wheel")
    # --out-dir keeps `dist/` out of the working tree, so running the suite leaves
    # nothing behind to be stale on the next run or committed by accident.
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out)],
        cwd=_ROOT,
        check=True,
        capture_output=True,
    )

    built = sorted(out.glob("*.whl"))
    assert built, f"uv build --wheel wrote no .whl into {out}"
    return built[-1]


def test_the_wheel_carries_py_typed(wheel) -> None:
    """`py.typed` must ship inside the package, or none of the annotations count.

    Inside `jointview/`, specifically. The marker is looked up next to the modules it
    speaks for, so a copy in the `dist-info` — or in the sdist alone — buys nothing.
    """
    names = zipfile.ZipFile(wheel).namelist()

    assert "jointview/py.typed" in names, (
        f"{wheel.name} does not carry jointview/py.typed, so every annotation in the "
        f"package reads as Any to a consumer's type checker (PEP 561). Check that "
        f"src/jointview/py.typed exists and that the build backend is not excluding it. "
        f"The wheel holds: {sorted(name for name in names if name.startswith('jointview/'))}"
    )
