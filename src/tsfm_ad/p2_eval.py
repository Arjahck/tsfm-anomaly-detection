"""Phase 2 scores, injection detection, false alarms, curves, red team and the MPS check (PLAN.md 15.6, D146). Reads
the Phase 2 cache; the red-team stage and the MPS check forecast through p2.rolling. Not a hashed source."""
from __future__ import annotations

import copy
import math
from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad import score
from tsfm_ad.cache import QCOLS
from tsfm_ad.p2 import (BASELINES, I05, I50, I95, Data, _inputs, _write, model_tag, read, redteam_clusters, rolling,
                        run_dir, span)

SCORES = ("band", "mae", "crps")


def scored(df: pl.DataFrame, eps: float, frozen: pl.DataFrame | None = None) -> pl.DataFrame:
    """band, mae, crps per row; with `frozen` (same keys) the dual score instead."""
    Q = df.select(QCOLS).to_numpy()
    y = df["y"].to_numpy()
    if frozen is not None:
        j = df.select("series", "t").join(frozen.select("series", "t", *QCOLS), on=["series", "t"], how="left")
        return df.select("series", "t", "label").with_columns(
            dual=pl.Series(score.dual(Q, j.select(QCOLS).to_numpy(), eps=eps)))
    return df.select("series", "t", "label").with_columns(
        band=pl.Series(score.band(y, Q[:, I05], Q[:, I95], eps)), mae=pl.Series(score.mae(y, Q[:, I50])),
        crps=pl.Series(score.crps(y, Q)))


def _chance(al: np.ndarray, keep: np.ndarray, n: int) -> float | None:
    """Share of n-minute windows lying wholly on normal minutes that hold at least one alarm (D151)."""
    if n > len(al):
        return None
    c, k = np.r_[0, np.cumsum(al & keep)], np.r_[0, np.cumsum(keep)]
    ok = (k[n:] - k[:-n]) == n
    return float(((c[n:] - c[:-n])[ok] > 0).mean()) if ok.any() else None


def _cov(al: np.ndarray, m: np.ndarray) -> float | None:
    return float(al[m].mean()) if m.any() else None


def detect(sc: pl.DataFrame, kind: str, thr: dict, man: pl.DataFrame, cfg: dict) -> tuple[list[dict], list[dict]]:
    """Per-injection detection and per-series false alarms on one seed's test scores (D146). `chance` is the
    detection rate the same window gets from false alarms alone; onset / interior / offset coverage use N = grace_min
    minutes after the start, the rest of the injection, and N minutes after its end (D151)."""
    s = cfg["score"]
    N = s["grace_min"]
    sc = sc.with_columns(alarm=pl.col(kind) > pl.col("series").replace_strict(thr, return_dtype=pl.Float64))
    by = {k[0]: g.sort("t") for k, g in sc.group_by("series")}
    keeps = {}
    for name, g in by.items():
        t = g["t"].to_numpy()
        assert (np.diff(t) == 1).all(), f"{name}: test minutes not contiguous"
        keep = np.ones(len(t), bool)
        for r in man.filter(pl.col("series") == name).iter_rows(named=True):
            keep &= ~((t >= r["start"] - s["fa_exclude_before_min"]) & (t < r["end"] + s["fa_exclude_after_min"]))
        keeps[name] = keep
    det = []
    for r in man.iter_rows(named=True):
        g = by[r["series"]]
        t, al, v = g["t"].to_numpy(), g["alarm"].to_numpy(), g[kind].to_numpy()
        w = (t >= r["start"]) & (t < r["end"] + N)
        hit = t[w & al]
        inside = (t >= r["start"]) & (t < r["end"])
        det.append({**{k: r[k] for k in ("seed", "inj_id", "type", "series", "group", "magnitude", "duration_min")},
                    "detected": bool(len(hit)), "latency_min": int(hit[0] - r["start"]) if len(hit) else None,
                    "coverage": _cov(al, inside),
                    "max_score_ratio": float(v[w].max() / thr[r["series"]]) if w.any() else None,
                    "chance": _chance(al, keeps[r["series"]], r["end"] + N - r["start"]),
                    "cov_onset": _cov(al, (t >= r["start"]) & (t < min(r["start"] + N, r["end"]))),
                    "cov_interior": _cov(al, (t >= r["start"] + N) & (t < r["end"])),
                    "cov_offset": _cov(al, (t >= r["end"]) & (t < r["end"] + N))})
    fa = []
    for name, g in by.items():
        al, keep = g["alarm"].to_numpy(), keeps[name]
        days = keep.sum() / 1440
        fa.append({"series": name, "normal_minutes": int(keep.sum()), "alarms": int(al[keep].sum()),
                   "fa_per_day": float(al[keep].sum() / days) if days else None})
    return det, fa


def evaluate(cfg: dict) -> None:
    """thresholds.csv, detections.csv, false_alarms.csv, curves.csv in results/phase2 (cache only)."""
    data, inputs = Data(cfg), {}
    out = Path(cfg["paths"]["results"])
    eps, pct = cfg["score"]["eps"], cfg["score"]["pct"]
    methods = [(r, k) for r in ("mv", "mv-cov", "mv-ff", "mv-frozen", *BASELINES) for k in SCORES] + [("mv-dual",
                                                                                                         "dual")]
    thr_rows, det_rows, fa_rows = [], [], []
    frozen_cache = {}
    for run, kind in methods:
        try:
            if run == "mv-dual":
                get = lambda part: scored(read(cfg, "mv", part, data), eps,  # noqa: E731
                                          frozen_cache.setdefault(part, read(cfg, "mv-frozen", part, data)))
            else:
                get = lambda part, run=run: scored(read(cfg, run, part, data), eps)  # noqa: E731
            cal = get("calib")
        except FileNotFoundError as e:
            print(f"p2 evaluate: {run} skipped ({e})")
            continue
        thr = {n: float(np.percentile(g[kind].to_numpy(), pct)) for (n,), g in cal.group_by("series")}
        thr_rows += [{"run": run, "score": kind, "series": n, "threshold": v} for n, v in thr.items()]
        for seed in cfg["inject"]["seeds"]:
            man = _inputs(data, f"seed{seed}", inputs)[2]
            d, f = detect(get(f"seed{seed}"), kind, thr, man, cfg)
            det_rows += [{"run": run, "score": kind, **x} for x in d]
            fa_rows += [{"run": run, "score": kind, "seed": seed, **x} for x in f]
    det, fa = pl.DataFrame(det_rows), pl.DataFrame(fa_rows).sort("run", "score", "seed", "series")
    pl.DataFrame(thr_rows).sort("run", "score", "series").write_csv(out / "thresholds.csv")   # stable row order
    det.write_csv(out / "detections.csv")
    fa.write_csv(out / "false_alarms.csv")
    curves = (det.group_by("run", "score", "type", "magnitude", "duration_min")
              .agg(n=pl.len(), detected=pl.col("detected").sum(), rate=pl.col("detected").mean(),
                   latency_median_min=pl.col("latency_min").median(), coverage_mean=pl.col("coverage").mean(),
                   chance_mean=pl.col("chance").mean(), cov_onset_mean=pl.col("cov_onset").mean(),
                   cov_interior_mean=pl.col("cov_interior").mean(), cov_offset_mean=pl.col("cov_offset").mean())
              .sort("run", "score", "type", "duration_min", "magnitude"))
    curves.write_csv(out / "curves.csv")
    fa_sum = (fa.group_by("run", "score").agg(fa_per_series_day=pl.col("alarms").sum()
                                               / (pl.col("normal_minutes").sum() / 1440))
              .sort("run", "score"))
    fa_sum.write_csv(out / "false_alarms_summary.csv")
    print(f"p2 evaluate: {det.height} detection rows, results in {out}")


# ---- red team (D146) ----

def redteam(cfg: dict) -> None:
    """mv rolling around each red-team cluster (history days, clean data); alarms against the mv calib thresholds."""
    from tsfm_ad import model_chronos2

    data = Data(cfg)
    H, w = cfg["forecast"]["H"], cfg["redteam"]["window_min"]
    clusters = redteam_clusters(cfg)
    d = run_dir(cfg, "mv", data)
    path = d / "redteam.parquet"
    if not path.exists():
        pipe = model_chronos2.load(cfg["model"], cfg["paths"]["hf_cache"])
        stats = {"forecasts": 0, "crossed": 0, "calls": 0, "seconds": 0.0}
        frames = []
        for first, last, _ in clusters:
            a = max(H * math.ceil(1440 / H), (first - w) // H * H)
            b = (last + w) // H * H + H
            frames.append(rolling(pipe, data, data.Z0, np.zeros_like(data.Z0, np.int8), a, b, cfg, False, stats))
        _write(pl.concat(frames).unique(["series", "t"]).sort("series", "t"), path, {"run": "mv", "part": "redteam"})
    sc = scored(pl.read_parquet(path), cfg["score"]["eps"])
    thr = pl.read_csv(Path(cfg["paths"]["results"]) / "thresholds.csv").filter(
        (pl.col("run") == "mv") & (pl.col("score") == "band"))
    thr = dict(zip(thr["series"], thr["threshold"]))
    sc = sc.with_columns(ratio=pl.col("band") / pl.col("series").replace_strict(thr, return_dtype=pl.Float64))
    rows = []
    for first, last, n in clusters:
        lo, hi = first - w, last + w + 1
        g = sc.filter((pl.col("t") >= lo) & (pl.col("t") < hi))
        ev = g.filter((pl.col("t") >= first) & (pl.col("t") <= last))
        top = g.sort("ratio", descending=True).head(1)
        rows.append({"first_minute": int(first), "last_minute": int(last), "day": int(first // 1440),
                     "events": int(n), "window_minutes": int(hi - lo),
                     "alarm_series_minutes": int((g["ratio"] > 1).sum()),
                     "alarms_per_hour": float((g["ratio"] > 1).sum() / ((hi - lo) / 60)),
                     "alarms_per_hour_during_events": float((ev["ratio"] > 1).sum() / max(1, (last - first + 1)) * 60),
                     "max_ratio": float(top["ratio"][0]) if top.height else None,
                     "max_ratio_series": top["series"][0] if top.height else None})
    pl.DataFrame(rows).write_csv(Path(cfg["paths"]["results"]) / "redteam.csv")
    print(f"p2 redteam: {len(clusters)} clusters")


# ---- MPS check (D54 for Phase 2, on the smoke days) ----

def mps_check(cfg: dict) -> dict:
    """mv rolling on calib + test of the smoke days on cpu and mps; relative rule of D130 and identical alarms."""
    from tsfm_ad import model_chronos2

    data = Data(cfg)
    Z, L, man, _ = data.seeded(cfg["inject"]["seeds"][0])
    res = {}
    for dev in ("cpu", "mps"):
        m = copy.deepcopy(cfg["model"])
        m["device"] = dev
        pipe = model_chronos2.load(m, cfg["paths"]["hf_cache"])
        st = {"forecasts": 0, "crossed": 0, "calls": 0, "seconds": 0.0}
        res[dev] = (rolling(pipe, data, data.Z0, np.zeros_like(Z, np.int8), *span(cfg, "calib"), cfg, False, st),
                    rolling(pipe, data, Z, L, *span(cfg, "test"), cfg, False, st))
    a = np.vstack([res["cpu"][i].select(QCOLS).to_numpy() for i in (0, 1)]).astype(np.float64)
    b = np.vstack([res["mps"][i].select(QCOLS).to_numpy() for i in (0, 1)]).astype(np.float64)
    rel = float((np.abs(a - b) / (np.abs(a) + 1)).max())
    eps, pct = cfg["score"]["eps"], cfg["score"]["pct"]
    alarms = []
    for dev in ("cpu", "mps"):
        cal, tst = scored(res[dev][0], eps), scored(res[dev][1], eps)
        thr = {n: float(np.percentile(g["band"].to_numpy(), pct)) for (n,), g in cal.group_by("series")}
        alarms.append((tst["band"] > tst["series"].replace_strict(thr, return_dtype=pl.Float64)).to_numpy())
    row = {"model": model_tag(cfg).rsplit("-", 1)[0], "run": "mv", "n_values": int(a.size),
           "max_abs_diff": float(np.abs(a - b).max()), "max_rel_diff": rel,
           "alarms_equal": bool((alarms[0] == alarms[1]).all()),
           "verdict": "pass" if rel <= 1e-3 and (alarms[0] == alarms[1]).all() else "fail"}
    out = Path(cfg["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame([row]).write_csv(out / "mps_check.csv")
    print(f"p2 MPS check: max rel {rel:.2e}, alarms equal {row['alarms_equal']} -> {row['verdict']}")
    return row
