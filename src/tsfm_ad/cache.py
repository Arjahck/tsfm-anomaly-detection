"""Forecast cache (PLAN.md 6.1, D34): cache/<dataset>/<model>/<setup>/<variant>@<hash8>/<split>/<file>.parquet.

Nothing here deletes or overwrites a forecast directory: a changed setting or changed code gives a new hash and
a new directory beside the old one. Readers recompute the hash and never fall back to a stale directory.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import polars as pl

from tsfm_ad import data
from tsfm_ad.config import forecast_hash, forecast_settings, run_key, with_variant

QUANTILE_LEVELS = (0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
                   0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.99)
QCOLS = [f"q{round(q * 100):02d}" for q in QUANTILE_LEVELS]   # q01, q05, ..., q50, ..., q95, q99

FORECAST_SCHEMA = {
    "file": pl.String, "channel": pl.String, "t": pl.Int32, "time": pl.Datetime("us"), "origin": pl.Int32,
    "h": pl.Int16, "ctx_len": pl.Int32, **{q: pl.Float32 for q in QCOLS},
    "y_true": pl.Float32, "label": pl.Int8, "substituted": pl.Boolean,
}
REF_SCHEMA = {"channel": pl.String, "h": pl.Int16, **{q: pl.Float32 for q in QCOLS}}
# results/<phase>/runs.csv (PLAN.md 12). `model_code` = the timestral commit or the chronos-forecasting pin (D122).
RUNS_COLUMNS = ["run_key", "split", "config", "forecast_hash", "device", "model_code", "revision", "started",
                "finished", "wallclock_s", "n_calls"]


def run_dir(cfg: dict, variant: str | None = None, extra=None) -> Path:
    """`<cache>/<dataset>/<model>/<setup>/<variant>@<hash8>`. `variant` is a kind override (rolling, ff, frozen,
    dual, cf-onset); None uses cfg's own. `extra` goes into the hash (e.g. the FF thresholds hash)."""
    c = with_variant(cfg, variant)
    rk = run_key(c)
    h = forecast_hash(c, extra=extra)
    return Path(cfg["paths"]["cache"]) / rk.dataset / rk.model / rk.setup / f"{rk.variant}@{h[:8]}"


def cache_path(cfg: dict, split: str, file: str, variant: str | None = None, extra=None) -> Path:
    return run_dir(cfg, variant, extra) / split / f"{file}.parquet"


def meta(cfg: dict, variant: str | None = None, extra=None) -> dict:
    """Content of meta.json: run key, full forecast hash, the hashed settings and `extra`."""
    c = with_variant(cfg, variant)
    return {"run_key": str(run_key(c)), "forecast_hash": forecast_hash(c, extra=extra),
            "settings": forecast_settings(c), "extra": extra, "config": cfg.get("_path")}


def _conform(df: pl.DataFrame) -> pl.DataFrame:
    schema = FORECAST_SCHEMA if "t" in df.columns else REF_SCHEMA
    if "substituted" not in df.columns and schema is FORECAST_SCHEMA:
        df = df.with_columns(substituted=pl.lit(False))
    missing = [c for c in schema if c not in df.columns]
    if missing:
        raise ValueError(f"cache frame lacks columns {missing}")
    return df.select([pl.col(c).cast(t) for c, t in schema.items()])


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write(df: pl.DataFrame, path: Path, meta: dict) -> None:
    """Write one cache parquet atomically (temp name, then rename) and meta.json in the run directory if missing.

    `path` is from cache_path (…/<variant>@<hash8>/<split>/<file>.parquet). Columns are cast to FORECAST_SCHEMA
    (or REF_SCHEMA for the frozen `ref` file); `substituted` defaults to False.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = path.parent.parent / "meta.json"
    if not meta_path.exists():
        _atomic_write_bytes(meta_path, json.dumps(meta, indent=1, default=str).encode())
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    _conform(df).write_parquet(tmp)
    os.replace(tmp, path)


def split_paths(cfg: dict, d: Path, split: str, files=None) -> list[Path]:
    """The parquet of every segment cfg lists for `split` (or of the named `files`) in run directory d, in file-name
    order. Raises when one is missing, so a partly forecast split is never read in part (D111)."""
    if files is None:
        files = [s.name for s in data.make_segments(cfg)[split]]
    paths = [Path(d) / split / f"{f}.parquet" for f in sorted(files)]
    missing = [p.name for p in paths if not p.exists()]
    if missing or not paths:
        raise FileNotFoundError(f"{Path(d) / split} lacks {missing or 'every file'}: run forecast first")
    return paths


def read(cfg: dict, split: str, variant: str | None = None, files=None, extra=None) -> pl.DataFrame:
    """Every cached file of one split (or the named `files`), concatenated in file-name order (see split_paths)."""
    d = run_dir(cfg, variant, extra)
    if not d.exists():
        raise FileNotFoundError(f"{d} does not exist: run forecast first")
    return pl.concat([pl.read_parquet(p) for p in split_paths(cfg, d, split, files)])


def read_ref(cfg: dict) -> pl.DataFrame:
    """The frozen forecast (columns channel, h, q01..q99) of cfg's model and setup."""
    path = run_dir(cfg, "frozen") / "ref" / "reference.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist: run forecast with variant frozen first")
    return pl.read_parquet(path)


CALLS_COLUMNS = ["T", "rows", "seconds", "crossed", "forecasts", "const_rows"]


def log_call(path: Path, T: int, rows: int, seconds: float, crossed=None, forecasts=None, const_rows=None) -> None:
    """Append one forecast call to a calls_<split>.csv: context length, rows, wall-clock seconds and, for Chronos-2,
    how many of its `forecasts` (target x h) had crossing quantiles that were sorted (D119) and how many rows were
    constant over the context (D128); empty for Timestral. A file written before D119 keeps its three columns."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    n = len(CALLS_COLUMNS) if new else len(path.open().readline().strip().split(","))
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CALLS_COLUMNS)
        row = [int(T), int(rows), f"{seconds:.6f}", *("" if v is None else int(v) for v in (crossed, forecasts,
                                                                                         const_rows))]
        w.writerow(row[:n])


def append_run(results, row: list) -> None:
    """Append one row (RUNS_COLUMNS order) to <results>/runs.csv. A file written before D122, whose header says
    `timestral_commit` where RUNS_COLUMNS says `model_code`, gets the new header; its rows stay as they are."""
    path = Path(results) / "runs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = path.read_text().splitlines(keepends=True)
        head = lines[0].rstrip("\r\n").split(",") if lines else []
        if head != RUNS_COLUMNS:
            if ["model_code" if c == "timestral_commit" else c for c in head] != RUNS_COLUMNS:
                raise ValueError(f"{path} has the columns {head}, expected {RUNS_COLUMNS}")
            _atomic_write_bytes(path, "".join([",".join(RUNS_COLUMNS) + "\n", *lines[1:]]).encode())
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(RUNS_COLUMNS)
        w.writerow(row)
