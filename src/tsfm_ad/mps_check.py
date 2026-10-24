"""MPS vs CPU check of D54 on the smoke slices, written to results/phase1/mps_check.csv (PLAN.md 6, 14, D15, D54).

For one (model, setup) of the config's model.name (chronos2; or a Timestral size): the rolling forecast of the smoke
calib and test files runs on cpu and on mps, both are scored with their own smoke calib thresholds, and the check
compares every quantile of every cached row and the test alarms (band score, top-3 mean, the setup's full channel
set). Pass (D130, Arthur's answer to Q18, relative form of D54) = max |q_mps - q_cpu| / (|q_cpu| + 1) <= 1e-3 and
identical alarms: 1e-3 z near zero, 0.1 % of the value for large values (P1_PCV02Z reaches about 510 fit-z, where
float32 rounding alone exceeds 1e-3 z). max_abs_diff and the gap without P1_PCV02Z are diagnostics. Rows are keyed by
model id, so each model has its own verdict.
"""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad import cache, forecast, score
from tsfm_ad.cache import QCOLS
from tsfm_ad.config import model_id

TOL = 1e-3
DIAG_CHANNEL = "P1_PCV02Z"   # tiny fit std, so values reach hundreds of fit-z (PLAN.md 3.4)
KEY = ["dataset", "model", "setup"]


def pair_cfg(cfg: dict, size: str | None, setup: str, device: str) -> dict:
    """cfg's model (a Timestral `size` if given) on `device`, rolling, in-file warm-up, for one setup."""
    c = copy.deepcopy(cfg)
    c["model"]["device"] = device
    if size is not None:
        c["model"]["size"] = size
    c["setup"] = setup
    c["variant"]["kind"] = "rolling"
    c["forecast"]["warmup"] = "in_file"
    return c


def _alarms(c: dict) -> tuple[np.ndarray, float]:
    d = cache.run_dir(c)
    cs = c["channels"]["setups"][c["setup"]]["channel_set"]
    s = pl.read_parquet(d / "scores" / cs / "agg_test.parquet").sort("file", "t")["band_topk"].to_numpy()
    thr = pl.read_parquet(d / "scores" / cs / "thresholds.parquet").filter(
        (pl.col("score") == "band") & (pl.col("agg") == "topk") & (pl.col("calib_source") == "calib"))
    t = float(thr["threshold"].item())
    return s > t, t


def check(cfg: dict, size: str | None, setup: str) -> dict:
    """Run (or reuse from the cache) cpu and mps rolling forecasts of one (model, setup), score both, compare."""
    cfgs = {dev: pair_cfg(cfg, size, setup, dev) for dev in ("cpu", "mps")}
    for c in cfgs.values():
        forecast.run_forecast(c, "all")
        score.run_score(c)
    q = {dev: pl.concat([cache.read(c, sp) for sp in ("calib", "test")]) for dev, c in cfgs.items()}
    j = q["cpu"].join(q["mps"], on=["file", "channel", "t"], suffix="_mps")
    if not (j.height == q["cpu"].height == q["mps"].height):
        raise ValueError(f"cpu and mps caches hold different rows ({q['cpu'].height} vs {q['mps'].height})")
    a = j.select(QCOLS).to_numpy().astype(np.float64)
    b = j.select([f"{c}_mps" for c in QCOLS]).to_numpy().astype(np.float64)
    diff = np.abs(a - b)
    other = (j["channel"] != DIAG_CHANNEL).to_numpy()
    (al_cpu, t_cpu), (al_mps, t_mps) = _alarms(cfgs["cpu"]), _alarms(cfgs["mps"])
    equal = bool(al_cpu.shape == al_mps.shape and (al_cpu == al_mps).all())
    max_abs = float(diff.max())
    max_rel = float((diff / (np.abs(a) + 1.0)).max())
    return {"dataset": cfg["dataset"]["key"], "model": model_id(cfgs["cpu"]),
            "setup": setup, "n_values": int(diff.size), "max_abs_diff": max_abs, "mean_abs_diff": float(diff.mean()),
            "alarms_equal": equal, "verdict": "pass" if max_rel <= TOL and equal else "fail",
            "max_abs_diff_excl_PCV02Z": float(diff[other].max()) if other.any() else None,
            "max_rel_diff": max_rel,
            "threshold_cpu": t_cpu, "threshold_mps": t_mps, "n_alarms_cpu": int(al_cpu.sum()),
            "n_alarms_mps": int(al_mps.sum()), "n_test_steps": int(al_cpu.size),
            "checked_at": datetime.now().isoformat(timespec="seconds")}


def write(row: dict, path: Path) -> None:
    """Upsert one check row into mps_check.csv (key: dataset, model, setup)."""
    path = Path(path)
    new = pl.DataFrame([row]).select(pl.all().cast(pl.String))
    if path.exists():
        old = pl.read_csv(path, infer_schema_length=0).join(new.select(KEY), on=KEY, how="anti")
        new = pl.concat([old, new], how="diagonal")
    path.parent.mkdir(parents=True, exist_ok=True)
    new.sort(KEY).write_csv(path)


def check_and_write(cfg: dict, size: str | None, setup: str, path: Path) -> None:
    row = check(cfg, size, setup)
    write(row, path)
    print(f"MPS check {row['dataset']} {row['model']} {setup}: max |diff| {row['max_abs_diff']:.2e} "
          f"(without {DIAG_CHANNEL} {row['max_abs_diff_excl_PCV02Z']:.2e}), max rel {row['max_rel_diff']:.2e}, "
          f"alarms equal {row['alarms_equal']} "
          f"-> {row['verdict']}")


def guard(cfg: dict, path: Path) -> None:
    """Refuse a non-smoke TSFM run on mps unless the check passed for its (resolution, model, setup) and no check
    row of the same model family (chronos2, timestral) failed (D15: one device for all headline runs)."""
    m = cfg["model"]
    if m["name"] == "baseline" or m["device"] != "mps" or cfg["dataset"]["key"].endswith("-smoke"):
        return
    hint = "D15: run on cpu (--device cpu)"
    if not Path(path).exists():
        raise RuntimeError(f"{path} is missing: run `tsfm-ad smoke` (the MPS check) first, or {hint}")
    df = pl.read_csv(path, infer_schema_length=0).filter(pl.col("model").str.starts_with(f"{m['name']}-"))
    bad = df.filter(pl.col("verdict") != "pass")
    if bad.height:
        raise RuntimeError(f"the MPS check failed for {bad.select(KEY).rows()}; {hint}")
    want = (f"{cfg['dataset']['key']}-smoke", model_id(cfg), cfg["setup"])
    if not df.filter(*[pl.col(k) == v for k, v in zip(KEY, want)]).height:
        raise RuntimeError(f"no MPS check row for {want}: add it to mps_check in the smoke config, or {hint}")
