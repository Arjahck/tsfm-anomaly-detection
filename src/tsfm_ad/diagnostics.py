"""quantile_diagnostics.csv (PLAN.md 14.5, 14.9 items 10-11, D133): how often Chronos-2's raw quantiles crossed and
how many constant rows the D128 guard zeroed (from the `calls_<split>.csv` files), and how often the forecast band is
wide enough to blind the band score (from the cache). Cache and results only, never the model.

One row per run key, hash8 and split. The width cut-offs (10, 100 and 1000 fit-z) are fixed and descriptive: no
score, threshold or selection reads this file.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from tsfm_ad import cache, latency, score
from tsfm_ad.config import TSFM_MODELS

BAND_CUTS = (10, 100)      # q95 - q05, fit-z
TAIL_CUTS = (100, 1000)    # q99 - q01, fit-z


def _width_stats(q: pl.DataFrame, prefix: str = "") -> dict:
    band, tail = q["q95"] - q["q05"], q["q99"] - q["q01"]
    n = q.height
    out = {f"{prefix}rows": n}
    for c in BAND_CUTS:
        out[f"{prefix}share_band_gt_{c}"] = float((band > c).sum() / n) if n else None
    for c in TAIL_CUTS:
        out[f"{prefix}share_tail_gt_{c}"] = float((tail > c).sum() / n) if n else None
    return out


def diag_rows(cfg: dict) -> pl.DataFrame:
    """The rows of one TSFM run (none for dual, which makes no forecast of its own, or for baselines)."""
    if cfg["model"]["name"] not in TSFM_MODELS or cfg["variant"]["kind"] == "dual":
        return pl.DataFrame()
    d = latency.calls_dir(cfg)
    keys = score.key_columns(cfg, d)
    calls = latency.read_calls(cfg)
    rows = []
    for split in sorted(calls["split"].unique().to_list()):
        c = calls.filter(pl.col("split") == split)
        row = {**keys, "device": cfg["model"]["device"], "split": split, "calls": c.height,
               "forecasts": int(c["forecasts"].sum()), "crossed": int(c["crossed"].sum()),
               "const_rows": int(c["const_rows"].sum())}
        row["share_crossed"] = row["crossed"] / row["forecasts"] if row["forecasts"] else None
        try:
            q = cache.read(cfg, split, extra=_extra(cfg))   # the frozen forecast (split ref) has no label column
        except FileNotFoundError:
            rows.append(row)
            continue
        band = q["q95"] - q["q05"]
        i = int(band.arg_max())
        row.update(_width_stats(q), band_max=float(band[i]), band_max_channel=q["channel"][i],
                   tail_max=float((q["q99"] - q["q01"]).max()))
        wide = q.filter(band > BAND_CUTS[0])
        row["top_channel_band_gt_10"] = (wide.group_by("channel").len().sort("len", descending=True)["channel"][0]
                                         if wide.height else None)
        if "label" in q.columns and split == "test":
            row.update(_width_stats(q.filter(pl.col("label") == 1), "attack_"))
        rows.append(row)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _extra(cfg: dict):
    from tsfm_ad import context  # FF only

    return context.ff_extra(cfg)


def write_diagnostics(cfgs: list[dict], results: Path) -> None:
    """quantile_diagnostics.csv for the given run configs (rows of the same run key, hash8 and split are replaced)."""
    parts = [df for df in (diag_rows(c) for c in cfgs) if df.height]
    if parts:
        score.upsert_csv(Path(results) / "quantile_diagnostics.csv",
                         pl.concat(parts, how="diagonal").unique(maintain_order=True), ["run_key", "hash8", "split"])
