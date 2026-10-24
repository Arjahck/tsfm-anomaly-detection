"""Splits and normalization without leakage (PLAN.md section 5, D7-D10)."""
from datetime import datetime

import numpy as np
import polars as pl

from conftest import needs_data
from tsfm_ad import data

TRAIN1_LAST = datetime(2020, 7, 12, 23, 59, 59)
STEPS_10S = {"test1": 4320, "test2": 11880, "test3": 10800, "test4": 3960, "test5": 9240,
             "train2": 22680, "train3": 47880, "reference": 8640,
             "train1a": 8640, "train1b": 8640, "train2a": 8640, "train2b": 8640}


def _rows(built, split):
    """(file, time) of every 1 s row a split's segments hold."""
    parts = [data.slice_rows(built["raw"][s.file], s.start, s.end).select(pl.lit(s.file).alias("file"), "time")
             for s in built["segments"][split]]
    return pl.concat(parts)


@needs_data
def test_step_counts(built):
    assert {k: v.height for k, v in built["z"].items()} == STEPS_10S


@needs_data
def test_calib_and_fit_disjoint(built):
    fit = _rows(built, "fit")
    assert _rows(built, "calib").join(fit, on=["file", "time"]).height == 0
    assert _rows(built, "calib").join(_rows(built, "calib2"), on=["file", "time"]).height == 0


@needs_data
def test_no_test_row_and_no_late_train1_row_in_train_segments(cfg, built):
    test_files = set(cfg["dataset"]["test_files"])
    for split in ("fit", "ref", "calib", "calib2"):
        rows = _rows(built, split)
        assert not set(rows["file"].unique()) & test_files, split
        late = rows.filter((pl.col("file") == "train1") & (pl.col("time") > TRAIN1_LAST))
        assert late.height == 0, split
        for s in built["segments"][split]:
            z = built["z"][s.name]
            assert z["attack"].sum() == 0, s.name
            if s.file == "train1":
                assert z["time"].max() <= TRAIN1_LAST


@needs_data
def test_norm_stats_equal_recomputation_on_train2_train3(built):
    """Recompute 10 s fit statistics with numpy reshapes, independent of downsample()."""
    roles = built["roles"].filter(pl.col("role") != "dropped")
    stats = built["stats"]
    cols = []
    for f in ("train2", "train3"):
        df = built["raw"][f]
        n = df.height // 10
        assert n * 10 == df.height
        block = []
        for c, role in roles.select("channel", "role").iter_rows():
            x = df[c].to_numpy().reshape(n, 10)
            block.append(x[:, -1] if role == "step" else x.mean(axis=1))
        cols.append(np.stack(block, axis=1))
    x = np.concatenate(cols)
    assert stats["channel"].to_list() == roles["channel"].to_list()
    np.testing.assert_allclose(stats["mean"].to_numpy(), x.mean(axis=0), rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(stats["std"].to_numpy(), x.std(axis=0, ddof=1), rtol=1e-8)


@needs_data
def test_norm_stats_ignore_test_and_calib_values(cfg, built):
    """Scaling every test file and train1 by 3 must leave the normalization statistics unchanged.

    In train1 only continuous and actuator channels are scaled: scaling a constant tag there would (rightly) change
    the roles, which are computed on fit + calib rows.
    """
    raw = dict(built["raw"])
    for f in cfg["dataset"]["test_files"]:
        raw[f] = raw[f].with_columns([pl.col(c) * 3.0 for c in data.tag_columns(raw[f])])
    moving = built["roles"].filter(pl.col("role").is_in(["continuous", "actuator"]))["channel"].to_list()
    raw["train1"] = raw["train1"].with_columns([pl.col(c) * 3.0 for c in moving])
    other = data.build(cfg, raw=raw)
    assert other["stats"].equals(built["stats"])


@needs_data
def test_fit_segments_are_z_scored(built):
    z = pl.concat([built["z"]["train2"], built["z"]["train3"]])
    ch = built["stats"]["channel"].to_list()
    x = z.select(ch).to_numpy().astype(np.float64)
    np.testing.assert_allclose(x.mean(axis=0), 0, atol=1e-4)
    np.testing.assert_allclose(x.std(axis=0, ddof=1), 1, atol=1e-4)
