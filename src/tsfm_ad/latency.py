"""latency.csv and size_latency.csv (PLAN.md sections 9, 12 and 14) from the `calls_<split>.csv` files
next to the cache, runs.csv and the metrics CSVs. Cache and results only, never the model.

Per-call seconds exclude system sleep (perf_counter, D80); runs.csv wall-clock includes it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad import cache, context, score
from tsfm_ad.config import (TSFM_MODELS, forecast_hash, model_params, model_tag, resolve_selected, run_key, steps,
                            with_variant)

CTX_BUCKETS = [(1, 512), (513, 2048), (2049, 8192), (8193, 32768)]


def calls_dir(cfg: dict) -> Path:
    """Where a run's forecast calls are logged: its own directory; for dual (no inference) the rolling run's."""
    if cfg["variant"]["kind"] == "dual":
        return cache.run_dir(cfg, "rolling")
    return cache.run_dir(cfg, extra=context.ff_extra(cfg))


def read_calls(cfg: dict) -> pl.DataFrame:
    """All calls_<split>.csv of a run (columns split, T, rows, seconds); empty if none were logged."""
    parts = [pl.read_csv(p).with_columns(split=pl.lit(p.stem.removeprefix("calls_")))
             for p in sorted(calls_dir(cfg).glob("calls_*.csv"))]
    empty = pl.DataFrame(schema={"T": pl.Int64, "rows": pl.Int64, "seconds": pl.Float64, "crossed": pl.Int64,
                                 "forecasts": pl.Int64, "const_rows": pl.Int64, "split": pl.String})
    return pl.concat([empty, *parts], how="diagonal_relaxed")


def _bucket(T: int) -> str:
    return next(f"{lo}-{hi}" for lo, hi in CTX_BUCKETS if lo <= T <= hi)


def latency_rows(cfg: dict) -> pl.DataFrame:
    """One row per split and context-length bucket: rows per call, number of calls, median and p90 seconds."""
    calls = read_calls(cfg)
    keys = score.key_columns(cfg, calls_dir(cfg))
    if calls.height == 0:
        return pl.DataFrame()
    calls = calls.with_columns(ctx_bucket=pl.col("T").map_elements(_bucket, return_dtype=pl.String))
    out = (calls.group_by("split", "ctx_bucket", maintain_order=True)
           .agg(rows_per_call=pl.col("rows").median(), n_calls=pl.len(), sec_median=pl.col("seconds").median(),
                sec_p90=pl.col("seconds").quantile(0.9, interpolation="linear"))
           .sort("split", "ctx_bucket"))
    return out.select(pl.lit(keys["run_key"]).alias("run_key"), pl.lit(keys["model"]).alias("model"),
                      pl.lit(cfg["model"]["device"]).alias("device"), pl.lit(keys["setup"]).alias("setup"),
                      pl.all(), *[pl.lit(keys[c]).alias(c) for c in ("dataset", "variant", "hash8")])


def write_latency(cfgs: list[dict], results: Path) -> None:
    """latency.csv for the given TSFM run configs (rows of the same run key are replaced). Dual runs make no
    forecast call of their own, so they get no rows."""
    runs = [c for c in cfgs if c["model"]["name"] in TSFM_MODELS and c["variant"]["kind"] != "dual"]
    parts = [df for df in (latency_rows(c) for c in runs) if df.height]
    if parts:
        score.upsert_csv(Path(results) / "latency.csv", pl.concat(parts, how="diagonal").unique(maintain_order=True),
                         ["run_key", "split", "ctx_bucket"])


def _row(path: Path, keys: dict, **eq) -> dict | None:
    """The last row of a results CSV for this run key and hash8 with the given column values (all as strings)."""
    if not path.exists():
        return None
    df = pl.read_csv(path, infer_schema_length=0).filter(
        (pl.col("run_key") == keys["run_key"]) & (pl.col("hash8") == keys["hash8"]),
        *[pl.col(k) == str(v) for k, v in eq.items()])
    return df.row(-1, named=True) if df.height else None


def _float(row: dict | None, col: str) -> float | None:
    return None if row is None or row.get(col) in (None, "") else float(row[col])


def size_row(cfg: dict, selected: bool) -> dict:
    """One size_latency.csv row: the run's model size, latency and headline results (PLAN.md 12)."""
    res, kind = Path(cfg["paths"]["results"]), cfg["variant"]["kind"]
    d = score.source_dir(cfg)
    if not d.exists():
        raise FileNotFoundError(f"{d} does not exist: run forecast first")
    keys = score.key_columns(cfg, d)
    calls = read_calls(cfg)
    split = "ref" if kind == "frozen" else "test"
    sec = calls.filter(pl.col("split") == split)["seconds"]
    fc_cfg = with_variant(cfg, "rolling") if kind == "dual" else cfg
    full_hash = forecast_hash(fc_cfg, extra=context.ff_extra(fc_cfg))
    wallclock, runs = None, res / "runs.csv"
    if runs.exists():   # one row per invocation that wrote files of the split (D116): their sum is the whole split
        r = pl.read_csv(runs, infer_schema_length=0).filter(
            (pl.col("run_key") == str(run_key(fc_cfg))) & (pl.col("forecast_hash") == full_hash)
            & (pl.col("split") == split))
        wallclock = float(r["wallclock_s"].cast(pl.Float64).sum()) if r.height else None
    cs = cfg["channels"]["setups"][keys["setup"]]["channel_set"]
    sc = "dual" if kind == "dual" else "band"
    m = _row(res / "metrics.csv", keys, channel_set=cs, score=sc, agg="topk", calib_source="calib")
    t = _row(res / "tapr.csv", keys, channel_set=cs, score=sc, agg="topk", config="headline")
    s = _row(res / "segments_summary.csv", keys, channel_set=cs, score=sc, agg="topk",
             N=steps(cfg, cfg["metrics"]["N_onset_s"]), stratum="all", ff_group="all")
    return {"run_key": keys["run_key"], "model": keys["model"], "params": model_params(cfg),
            "device": cfg["model"]["device"], "setup": keys["setup"], "variant": keys["variant"], "channel_set": cs,
            "selected": selected, "sec_per_call_median": float(np.median(sec.to_numpy())) if len(sec) else None,
            "test_wallclock_s": wallclock, "roc_auc": _float(m, "roc_auc"),
            "pr_auc": _float(m, "pr_auc"), "tapr_f1": _float(t, "F1"), "onset_cov_mean": _float(s, "onset_cov_mean"),
            "interior_cov_mean": _float(s, "interior_cov_mean"), "dataset": keys["dataset"], "hash8": keys["hash8"]}


def write_size_latency(entries: list[tuple[dict, bool]], results: Path) -> None:
    """size_latency.csv from (run cfg, selected) pairs: the best setup and unselected uni rolling per size. One row
    per (dataset, model, selected); an entry that is skipped also loses its old row (D114)."""
    rows, gone = [], []
    for c, sel in entries:
        try:
            rows.append(size_row(resolve_selected(c), sel))
        except (FileNotFoundError, LookupError, ValueError) as e:   # a run that did not happen is not a row
            print(f"size_latency: {model_tag(c)} {c['setup']}/{c['variant']['kind']} skipped: {e}")
            gone.append({"dataset": c["dataset"]["key"], "model": model_tag(c), "selected": str(sel).lower()})
    path = Path(results) / "size_latency.csv"
    if gone and path.exists():
        old = pl.read_csv(path, infer_schema_length=0)
        old.join(pl.DataFrame(gone), on=["dataset", "model", "selected"], how="anti").write_csv(path)
    if rows:
        score.upsert_csv(path, pl.DataFrame(rows, infer_schema_length=None), ["dataset", "model", "selected"])
