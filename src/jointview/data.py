"""Getting a DataFrame into the app.

The app is handed a path on the command line; when there is none it falls back to
a generated frame so that ``marimo run app.py`` works out of the box.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import polars as pl

READERS: dict[str, Callable[[Path], pl.DataFrame]] = {
    ".arrow": pl.read_ipc,
    ".csv": pl.read_csv,
    ".feather": pl.read_ipc,
    ".ipc": pl.read_ipc,
    ".json": pl.read_json,
    ".ndjson": pl.read_ndjson,
    ".parquet": pl.read_parquet,
    ".tsv": lambda p: pl.read_csv(p, separator="\t"),
}


def load_frame(path: str | Path | None) -> pl.DataFrame:
    """Read a DataFrame from ``path``, or build the demo frame when it is None."""
    if path is None or path == "":
        return demo_frame()

    file = Path(path).expanduser()
    if not file.exists():
        raise FileNotFoundError(f"no such file: {file}")

    reader = READERS.get(file.suffix.lower())
    if reader is None:
        supported = ", ".join(sorted(READERS))
        raise ValueError(f"cannot read {file.suffix or file.name!r}; supported: {supported}")

    return reader(file)


def demo_frame(rows: int = 2_000, seed: int = 42) -> pl.DataFrame:
    """A frame with a mix of dtypes and a few deliberately correlated pairs."""
    rng = np.random.default_rng(seed)
    start = date(2020, 1, 1)

    # A latent factor drives returns, so return/factor is tight and the rest is not.
    factor = rng.normal(0.0, 1.0, rows)
    beta = rng.normal(1.0, 0.35, rows)
    idiosyncratic = rng.normal(0.0, 1.0, rows)

    returns = 0.011 * (beta * factor + idiosyncratic)
    volatility = 0.09 + 0.04 * rng.chisquare(3, rows) / 3.0

    return pl.DataFrame(
        {
            "date": pl.date_range(start, start + timedelta(days=rows - 1), "1d", eager=True),
            "sector": rng.choice(["energy", "financials", "health", "tech"], rows),
            "factor": factor,
            "beta": beta,
            "returns": returns,
            "volatility": volatility,
            # Heavy right tail: log-normal, so the marginal is worth looking at.
            "volume": np.exp(rng.normal(12.0, 0.9, rows)),
            "spread_bps": 4.0 + 60.0 * volatility + rng.exponential(2.0, rows),
            "noise": rng.normal(0.0, 1.0, rows),
        }
    )
