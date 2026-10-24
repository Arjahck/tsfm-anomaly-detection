"""Scores from the forecast cache (PLAN.md section 7, D17-D20, D49-D51). Reads the cache only, never the model.

run_score(cfg) writes, under the run directory `<variant>@<hash8>/scores/` (overwritten on every run):
  manifest.json                        score settings, scored channel sets, score columns, splits
  <channel_set>/agg_<split>.parquet    one row per scored step: file, t, time, origin, h, label, <score>_<agg>, ...
  <channel_set>/thresholds.parquet     score, agg, smooth, pct, calib_source, threshold, n_calib_steps
  <full set>/scores_<split>.parquet    one row per scored step and channel: file, t, origin, channel, <score>, ...
and upserts results/<phase>/thresholds.csv.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad import cache, data
from tsfm_ad.cache import QCOLS, QUANTILE_LEVELS
from tsfm_ad.config import run_key, steps

I05, I50, I95 = (QUANTILE_LEVELS.index(q) for q in (0.05, 0.50, 0.95))
STEP_COLS = ["file", "t", "time", "origin", "h", "label"]
THRESHOLD_KEY = ["run_key", "channel_set", "score", "agg", "smooth", "pct", "calib_source"]


# ---- scores (one value per channel and scored step) ----

def midpoint_weights(levels=QUANTILE_LEVELS) -> np.ndarray:
    """Cell widths with edges at 0, the midpoints between neighbouring levels, and 1; they sum to 1."""
    lv = np.asarray(levels, np.float64)
    return np.diff(np.concatenate([[0.0], (lv[1:] + lv[:-1]) / 2, [1.0]]))


def band(y, q05, q95, eps) -> np.ndarray:
    """max(0, y - q95, q05 - y) / (q95 - q05 + eps) (D17)."""
    y, q05, q95 = (np.asarray(a, np.float64) for a in (y, q05, q95))
    return np.maximum(0.0, np.maximum(y - q95, q05 - y)) / (q95 - q05 + eps)


def crps(y, Q, levels=QUANTILE_LEVELS) -> np.ndarray:
    """2 * sum_i w_i * pinball_tau_i(y - q_i), midpoint-rule weights w. Q is (n, len(levels))."""
    tau = np.asarray(levels, np.float64)
    u = np.asarray(y, np.float64)[:, None] - np.asarray(Q, np.float64)
    return 2.0 * ((u * (tau - (u < 0))) @ midpoint_weights(levels))


def mae(y, q50) -> np.ndarray:
    return np.abs(np.asarray(q50, np.float64) - np.asarray(y, np.float64))


def dual(Q_recent, Q_frozen, levels=QUANTILE_LEVELS, eps=0.1) -> np.ndarray:
    """Quantile Wasserstein-1 between the recent and frozen forecasts over the frozen band width (D27). No y."""
    lv = list(levels)
    Qr, Qf = np.asarray(Q_recent, np.float64), np.asarray(Q_frozen, np.float64)
    width = Qf[:, lv.index(0.95)] - Qf[:, lv.index(0.05)] + eps
    return (np.abs(Qr - Qf) @ midpoint_weights(levels)) / width


def frozen_rows(seg, ref: pl.DataFrame, W: int, H: int) -> pl.DataFrame:
    """Scored steps t >= W of a prepared segment on the rolling origin grid (origin = W + kH, h = t - origin + 1),
    with y_true and label from the segment, joined to the frozen quantiles on (channel, h). ctx_len is null."""
    t = np.arange(W, len(seg), dtype=np.int32)
    origin = W + ((t - W) // H) * H
    base = pl.DataFrame({"t": t, "time": seg.time[W:], "origin": origin, "h": (t - origin + 1).astype(np.int16),
                         "label": seg.labels[W:]}).with_columns(file=pl.lit(seg.name))
    channels = ref["channel"].unique(maintain_order=True).to_list()
    Y = seg.rows(channels)[:, W:]
    rows = pl.concat([base.with_columns(channel=pl.lit(c), y_true=pl.Series(Y[i])) for i, c in enumerate(channels)])
    out = rows.join(ref.with_columns(pl.col("h").cast(pl.Int16)), on=["channel", "h"], how="left")
    if out[QCOLS[0]].null_count():
        raise ValueError(f"the frozen forecast lacks some (channel, h) of {seg.name}")
    out = out.with_columns(ctx_len=pl.lit(None, pl.Int32), substituted=pl.lit(False))
    return out.select([pl.col(c).cast(dt) for c, dt in cache.FORECAST_SCHEMA.items()])


# ---- aggregation over the channels of a set, smoothing, threshold ----

def aggregate(S, how: str, k: int = 3) -> np.ndarray:
    """S is (steps, channels) of one channel set. topk = mean of the k largest (D19), max, or mean."""
    S = np.asarray(S, np.float64)
    if how == "max":
        return S.max(axis=1)
    if how == "mean":
        return S.mean(axis=1)
    if how == "topk":
        k = min(k, S.shape[1])
        return np.partition(S, S.shape[1] - k, axis=1)[:, -k:].mean(axis=1)
    raise ValueError(f"unknown aggregation {how!r}")


def smooth(s, k) -> np.ndarray:
    """Trailing mean over k steps (fewer at the start). k None or <= 1 leaves s unchanged."""
    s = np.asarray(s, np.float64)
    if not k or k <= 1:
        return s
    c = np.concatenate([[0.0], np.cumsum(s)])
    n = np.arange(1, len(s) + 1)
    lo = np.maximum(n - k, 0)
    return (c[n] - c[lo]) / (n - lo)


def threshold(calib_scores, pct: float) -> float:
    """The pct-th percentile (linear interpolation) of the aggregated calib scores (D20)."""
    x = np.asarray(calib_scores, np.float64)
    if x.size == 0 or np.isnan(x).any():
        raise ValueError("calib scores are empty or contain NaN")
    return float(np.percentile(x, pct))


# ---- run directory, channel sets, results CSVs ----

def source_dir(cfg: dict) -> Path:
    """The run's hashed directory, recomputed from the current config and code. An FF hash also covers the FF
    thresholds, which context.ff_extra recomputes from the base rolling calib cache."""
    from tsfm_ad import context  # FF only; context imports nothing heavy

    return cache.run_dir(cfg, extra=context.ff_extra(cfg))


def key_columns(cfg: dict, d: Path) -> dict:
    """Run-key columns carried by every results row."""
    rk = run_key(cfg)
    return {"run_key": str(rk), "dataset": rk.dataset, "model": rk.model, "setup": rk.setup,
            "variant": rk.variant, "hash8": d.name.split("@")[-1]}


def upsert_csv(path, df: pl.DataFrame, key: list[str]) -> None:
    """Replace the rows of `path` whose key matches a row of df, keep every other row, append df."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = df.select(pl.all().cast(pl.String))
    if path.exists():
        old = pl.read_csv(path, infer_schema_length=0)
        if all(c in old.columns for c in key):
            old = old.join(new.select(key).unique(), on=key, how="anti", nulls_equal=True)
        new = pl.concat([old, new], how="diagonal")
    new.sort("run_key", maintain_order=True).write_csv(path)   # rows of a run stay together, in their order


def scored_sets(cfg: dict, channels) -> dict[str, list[str]]:
    """Every channel set (incl. the -noPCV02Z and restricted views) whose channels were all forecast (D49, D50)."""
    have = set(channels)
    sets = {n: m for n, m in data.channel_sets(cfg).items() if set(m) <= have}
    if not sets:
        raise ValueError(f"no channel set is covered by the {len(have)} forecast channels")
    return sets


def score_columns(cfg: dict, kind: str) -> list[tuple[str, str, str]]:
    """(score, agg, agg label) triples; `mean` only with mae; a smoothing k is appended to the agg label."""
    sm = cfg["score"].get("smooth")
    kinds = ["dual"] if kind == "dual" else list(cfg["score"]["kinds"])
    out = []
    for kd in kinds:
        aggs = [a for a in cfg["score"]["agg"] if a != "mean"] + (["mean"] if kd == "mae" else [])
        out += [(kd, a, a if not sm or sm <= 1 else f"{a}-s{sm}") for a in aggs]
    return out


def read_manifest(cfg: dict, d: Path) -> dict:
    """The scores manifest of run directory d; it must match cfg's current score settings."""
    if not d.exists():
        raise FileNotFoundError(f"{d} does not exist: run forecast first, then score")
    path = d / "scores" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run score first")
    man = json.loads(path.read_text())
    if man["score"] != json.loads(json.dumps(cfg["score"])):
        raise ValueError(f"scores in {d} were made with other score settings: run score first")
    return man


# ---- run_score ----

def _splits(cfg: dict, kind: str, src: Path) -> list[str]:
    """Calib sources to threshold on: the listed ones, plus calib2 when its forecasts are cached (D51)."""
    listed = list(cfg["score"]["calib_sources"])
    if kind == "frozen":
        have = {s for s, segs in data.make_segments(cfg).items() if segs}
    else:
        have = {p.name for p in src.iterdir() if p.is_dir() and any(p.glob("*.parquet"))} if src.exists() else set()
    missing = [s for s in listed + ["test"] if s not in have]
    if missing:
        raise FileNotFoundError(f"no forecasts for split(s) {missing} in {src}: run forecast first")
    return listed + (["calib2"] if "calib2" in have and "calib2" not in listed and kind != "frozen" else [])


def _frames(cfg, kind, paths, split, ref, W, H):
    """Cache rows of one split, one file at a time (frozen: built from the prepared segments; dual: + ref)."""
    if kind == "frozen":
        for seg in data.load_split(cfg, split):
            yield frozen_rows(seg, ref, W, H)
        return
    for p in paths[split]:
        df = pl.read_parquet(p)
        if kind == "dual":
            fq = ref.rename({q: f"{q}_f" for q in QCOLS}).with_columns(pl.col("h").cast(pl.Int16))
            df = df.join(fq, on=["channel", "h"], how="left")
            if df[f"{QCOLS[0]}_f"].null_count():
                raise ValueError(f"the frozen forecast lacks some (channel, h) of {p}")
        yield df


def _channel_scores(df: pl.DataFrame, kinds, eps) -> dict[str, np.ndarray]:
    y = df["y_true"].to_numpy().astype(np.float64)
    Q = df.select(QCOLS).to_numpy().astype(np.float64)
    fns = {"band": lambda: band(y, Q[:, I05], Q[:, I95], eps), "crps": lambda: crps(y, Q),
           "mae": lambda: mae(y, Q[:, I50]),
           "dual": lambda: dual(Q, df.select([f"{q}_f" for q in QCOLS]).to_numpy(), eps=eps)}
    return {kd: fns[kd]() for kd in kinds}


def _aggregate_file(df, scores, sets, combos, k, sm) -> dict[str, pl.DataFrame]:
    """One file: per channel set, one row per step (unique (t, origin)) with every aggregated score column."""
    channels = sorted(df["channel"].unique().to_list())
    key = df["t"].to_numpy().astype(np.int64) * (1 << 32) + df["origin"].to_numpy().astype(np.int64)
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    ci = df["channel"].replace_strict(channels, list(range(len(channels))), return_dtype=pl.Int64).to_numpy()
    if len(np.unique(inv * len(channels) + ci)) != df.height:
        raise ValueError(f"duplicate (t, origin, channel) rows in {df['file'][0]}")
    mats = {}
    for kd, v in scores.items():
        mats[kd] = np.full((len(first), len(channels)), np.nan)
        mats[kd][inv, ci] = v
    info = df[first].select(STEP_COLS)
    out = {}
    for name, members in sets.items():
        idx = [channels.index(c) for c in members]
        cols = {}
        for kd, ag, label in combos:
            sub = mats[kd][:, idx]
            if np.isnan(sub).any():
                raise ValueError(f"steps without a score for some channels of {name} in {df['file'][0]}")
            cols[f"{kd}_{label}"] = smooth(aggregate(sub, ag, k), sm)
        out[name] = info.with_columns(**cols)
    return out


def run_score(cfg: dict) -> None:
    kind = cfg["variant"]["kind"]
    d = source_dir(cfg)
    W, H = steps(cfg, cfg["forecast"]["W_s"]), cfg["forecast"]["H"]
    sc = cfg["score"]
    sm, pct, eps = sc.get("smooth"), sc["threshold_pct"], sc["eps"]
    src = cache.run_dir(cfg, "rolling") if kind == "dual" else d
    if kind != "frozen" and not src.exists():
        raise FileNotFoundError(f"{src} does not exist: run forecast first")
    ref = cache.read_ref(cfg) if kind in ("frozen", "dual") else None
    sources = [] if kind == "cf-onset" else _splits(cfg, kind, src)
    # every file of every split must be cached before anything is written (D111)
    paths = {} if kind == "frozen" else {sp: cache.split_paths(cfg, src, sp) for sp in sources + ["test"]}
    combos = score_columns(cfg, kind)
    kinds = list(dict.fromkeys(kd for kd, _, _ in combos))
    sets, full, agg = None, None, {}
    for split in sources + ["test"]:
        parts, chan_parts = {}, []
        for df in _frames(cfg, kind, paths, split, ref, W, H):
            if sets is None:
                sets = scored_sets(cfg, df["channel"].unique().to_list())
                full = max(sets, key=lambda n: len(sets[n]))
            scores = _channel_scores(df, kinds, eps)
            for name, a in _aggregate_file(df, scores, sets, combos, sc["k"], sm).items():
                parts.setdefault(name, []).append(a)
            keep = df["channel"].is_in(sets[full]).to_numpy()
            chan_parts.append(df.filter(keep).select("file", "t", "origin", "channel")
                              .with_columns(**{kd: pl.Series(v[keep], dtype=pl.Float32) for kd, v in scores.items()}))
        if not parts:
            raise FileNotFoundError(f"no cached forecasts for split {split} in {src}: run forecast first")
        for name in sets:
            agg[name, split] = pl.concat(parts[name])
            out = d / "scores" / name
            out.mkdir(parents=True, exist_ok=True)
            agg[name, split].write_parquet(out / f"agg_{split}.parquet")
        pl.concat(chan_parts).write_parquet(d / "scores" / full / f"scores_{split}.parquet")
    keys = key_columns(cfg, d)
    rows = []
    for name in sets:
        thr = [{"channel_set": name, "score": kd, "agg": label, "smooth": sm, "pct": float(pct), "calib_source": s,
                "threshold": threshold(agg[name, s][f"{kd}_{label}"], pct), "n_calib_steps": agg[name, s].height}
               for s in sources for kd, _, label in combos]
        thr_df = pl.DataFrame(thr, schema={"channel_set": pl.String, "score": pl.String, "agg": pl.String,
                                           "smooth": pl.Int64, "pct": pl.Float64, "calib_source": pl.String,
                                           "threshold": pl.Float64, "n_calib_steps": pl.Int64})
        thr_df.write_parquet(d / "scores" / name / "thresholds.parquet")
        rows += thr
    manifest = {**keys, "kind": kind, "score": cfg["score"], "sets": sets, "full_set": full,
                "columns": [[kd, label] for kd, _, label in combos], "calib_sources": sources,
                "splits": sources + ["test"], "W": W, "H": H}
    (d / "scores" / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str))
    if rows:
        upsert_csv(Path(cfg["paths"]["results"]) / "thresholds.csv",
                   pl.DataFrame(rows).select(pl.lit(keys["run_key"]).alias("run_key"), pl.all(),
                                             *[pl.lit(keys[c]).alias(c) for c in list(keys)[1:]]),
                   THRESHOLD_KEY)
    print(f"scored {keys['run_key']}@{keys['hash8']}: {len(sets)} channel sets, splits {sources + ['test']}, "
          f"{len(rows)} thresholds")
