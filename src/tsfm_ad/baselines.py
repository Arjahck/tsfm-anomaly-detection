"""Experiment 5 honesty baselines in the forecast cache schema (PLAN.md section 8, D28, D49).

Each baseline returns 21 quantiles for every scored step t >= W of a segment, on the same origin grid as the
TSFM rolling forecasts (o = W, W + H, ...; h = t - o + 1), for all non-constant channels of the segment:

- robustz: median m and MAD of the trailing `window` steps before o; band m + Phi^-1(tau) * 1.4826 * MAD.
- lastvalue: y(o - 1) + Q_tau(Delta_h), Delta_h = y(s + h) - y(s) over the fit segments, per channel and h.
- seasonal-refday: the reference day at the same clock time + Q_tau(D), D = y(s) - y(s - 24 h) within each fit
  segment, per channel. No in-file lag: it never reads the segment it forecasts.

`ctx_len` is the number of in-file steps a forecast reads: min(o, window), 1 and 0. Run scope: D82, D83.
"""
from __future__ import annotations

import copy
import time
from datetime import datetime
from statistics import NormalDist

import numpy as np
import polars as pl

from tsfm_ad import cache, data
from tsfm_ad.cache import QCOLS, QUANTILE_LEVELS
from tsfm_ad.config import run_key, steps

BASELINES = ("robustz", "lastvalue", "seasonal-refday")
MAD_TO_SD = 1.4826
Z_TAU = np.array([NormalDist().inv_cdf(q) for q in QUANTILE_LEVELS])
LEVELS = np.array(QUANTILE_LEVELS)


def baseline_cfg(cfg: dict, name: str) -> dict:
    """cfg of one baseline run: model `baseline`, setup = the baseline name, variant kind rolling."""
    if name not in BASELINES:
        raise ValueError(f"unknown baseline {name!r}; expected one of {BASELINES}")
    c = copy.deepcopy(cfg)
    c["model"]["name"] = "baseline"
    c["setup"] = name
    c["variant"]["kind"] = "rolling"
    return c


def _grid(L: int, W: int, H: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scored steps t = W..L-1 with their origin o = W + kH and horizon h = t - o + 1."""
    if not 0 < W < L:
        raise ValueError(f"need 0 < W < L, got W={W}, L={L}")
    t = np.arange(W, L)
    o = W + (t - W) // H * H
    return t, o, t - o + 1


def _frame(seg: data.SegmentData, W: int, H: int, Q: np.ndarray, ctx_len: np.ndarray) -> pl.DataFrame:
    """Long cache rows, channel-major (channel, then t) like forecast.py. Q: (C, n, 21) for t = W..L-1;
    ctx_len: (n,) per scored step."""
    t, o, h = _grid(len(seg), W, H)
    C, n = Q.shape[0], len(t)
    q = Q.reshape(C * n, len(QCOLS))
    cols = {"channel": pl.Series(seg.channels).gather(np.repeat(np.arange(C), n)), "t": np.tile(t, C),
            "time": np.tile(seg.time[t], C), "origin": np.tile(o, C), "h": np.tile(h, C),
            "ctx_len": np.tile(ctx_len, C), **{name: q[:, i] for i, name in enumerate(QCOLS)},
            "y_true": seg.Z[:, t].reshape(-1), "label": np.tile(seg.labels[t], C)}
    return pl.DataFrame(cols).with_columns(file=pl.lit(seg.name), substituted=pl.lit(False))


def robust_z(seg: data.SegmentData, H: int, W: int, window: int = 360) -> pl.DataFrame:
    """Trailing robust z band at each origin: Z[:, max(0, o - window):o] only."""
    t, o, _ = _grid(len(seg), W, H)
    origins = np.unique(o)
    Qo = np.empty((len(origins), seg.Z.shape[0], len(QCOLS)), np.float32)
    for i, oo in enumerate(origins):
        x = seg.Z[:, max(0, oo - window):oo]
        m = np.median(x, axis=1)
        mad = np.median(np.abs(x - m[:, None]), axis=1)
        Qo[i] = m[:, None] + Z_TAU[None, :] * MAD_TO_SD * mad[:, None]
    oi = np.searchsorted(origins, o)
    Q = Qo[oi].transpose(1, 0, 2)                   # (C, n, 21)
    return _frame(seg, W, H, Q, np.minimum(o, window))


def change_quantiles(fit_segs: list[data.SegmentData], H: int, channels: list[str]) -> np.ndarray:
    """(C, H, 21) quantiles of Delta_h = y(s + h) - y(s), pooled over the fit segments (never across them)."""
    X = [s.rows(channels) for s in fit_segs]
    out = np.empty((len(channels), H, len(QCOLS)), np.float32)
    for h in range(1, H + 1):
        d = np.concatenate([x[:, h:] - x[:, :-h] for x in X if x.shape[1] > h], axis=1)
        out[:, h - 1] = np.quantile(d, LEVELS, axis=1).T
    return out


def last_value(seg: data.SegmentData, fit_segs: list[data.SegmentData], H: int, W: int,
               dq: np.ndarray | None = None) -> pl.DataFrame:
    """y(o - 1) plus the fit-set h-step change quantiles. `dq` = precomputed change_quantiles(fit_segs, H, ...)."""
    if dq is None:
        dq = change_quantiles(fit_segs, H, seg.channels)
    t, o, h = _grid(len(seg), W, H)
    last = seg.Z[:, o - 1]                          # (C, n): the value just before each step's origin
    Q = last[:, :, None] + dq[:, h - 1, :]
    return _frame(seg, W, H, Q, np.ones_like(o))


def seasonal_quantiles(fit_segs: list[data.SegmentData], lag: int, channels: list[str]) -> np.ndarray:
    """(C, 21) quantiles of D = y(s) - y(s - lag) within each fit segment."""
    d = [x[:, lag:] - x[:, :-lag] for x in (s.rows(channels) for s in fit_segs) if x.shape[1] > lag]
    if not d:
        raise ValueError(f"no fit segment is longer than the {lag}-step season")
    return np.quantile(np.concatenate(d, axis=1), LEVELS, axis=1).T.astype(np.float32)


def _sec_of_day(t: np.ndarray) -> np.ndarray:
    return ((t - t.astype("datetime64[D]")) // np.timedelta64(1, "s")).astype(np.int64)


def seasonal_refday(seg: data.SegmentData, ref_seg: data.SegmentData, fit_segs: list[data.SegmentData], H: int,
                    W: int, season_s: int = 86400, dq: np.ndarray | None = None) -> pl.DataFrame:
    """The reference day's value at the same clock time plus fit-set day-over-day residual quantiles."""
    res = int((seg.time[1] - seg.time[0]) // np.timedelta64(1, "s"))
    lag = season_s // res
    ref_res = (np.diff(ref_seg.time) // np.timedelta64(1, "s")).astype(np.int64)
    if len(ref_seg) != lag or season_s % res or not (ref_res == res).all():
        raise ValueError(f"reference must be one contiguous {season_s} s season at {res} s ({lag} steps); "
                         f"got {len(ref_seg)} steps")
    if dq is None:
        dq = seasonal_quantiles(fit_segs, lag, seg.channels)
    t, o, _ = _grid(len(seg), W, H)
    ref0 = _sec_of_day(ref_seg.time[:1])[0]
    idx = ((_sec_of_day(seg.time[t]) - ref0) % season_s) // res
    R = ref_seg.rows(seg.channels)[:, idx]          # (C, n)
    Q = R[:, :, None] + dq[:, None, :]
    return _frame(seg, W, H, Q, np.zeros_like(o))


def _splits(split: str) -> list[str]:
    if split == "all":
        return ["calib", "test"]
    if split == "ref":
        print("baselines: no `ref` split (only the frozen variant has one); nothing to do")
        return []
    return [split]


def run_baselines(cfg: dict, split: str) -> None:
    """Write robustz, lastvalue and seasonal-refday forecasts to the cache (or only cfg's setup if it is one of
    them). `split` all = calib + test. Files whose parquet exists are skipped."""
    if cfg["forecast"]["warmup"] != "in_file":
        raise ValueError("baselines read in-file history only; use forecast.warmup: in_file")
    names = [cfg["setup"]] if cfg["setup"] in BASELINES else list(BASELINES)
    H, W = cfg["forecast"]["H"], steps(cfg, cfg["forecast"]["W_s"])
    window = steps(cfg, cfg["baselines"]["robustz_window_s"])
    season_s = cfg["baselines"]["season_s"]
    splits = _splits(split)
    segs = {s: data.load_split(cfg, s) for s in splits}
    if not any(segs.values()):
        return
    fit = data.load_split(cfg, "fit")
    ref = data.load_split(cfg, "ref")[0]
    channels = next(seg for v in segs.values() for seg in v).channels
    res = cfg["dataset"]["resolution_s"]
    dq = {"lastvalue": None, "seasonal-refday": None}
    for name in names:
        bcfg = baseline_cfg(cfg, name)
        rk, meta = run_key(bcfg), cache.meta(bcfg)
        for s in splits:
            started, t_split, n_files = datetime.now().isoformat(timespec="seconds"), time.time(), 0
            for seg in segs[s]:
                path = cache.cache_path(bcfg, s, seg.name)
                if path.exists():
                    print(f"{rk} {s}/{seg.name}: cached, skipped")
                    continue
                if seg.channels != channels:
                    raise ValueError(f"{seg.name} has a different channel list")
                t0, n_files = time.time(), n_files + 1
                if name == "robustz":
                    df = robust_z(seg, H, W, window)
                elif name == "lastvalue":
                    if dq[name] is None:
                        dq[name] = change_quantiles(fit, H, channels)
                    df = last_value(seg, fit, H, W, dq[name])
                else:
                    if dq[name] is None:
                        dq[name] = seasonal_quantiles(fit, season_s // res, channels)
                    df = seasonal_refday(seg, ref, fit, H, W, season_s, dq[name])
                cache.write(df, path, meta)
                print(f"{rk} {s}/{seg.name}: {df.height} rows in {time.time() - t0:.1f} s")
            if n_files:
                _append_run(cfg, s, meta, started, time.time() - t_split)
        print(f"{rk}: {cache.run_dir(bcfg)}")


def _append_run(cfg: dict, split: str, meta: dict, started: str, wall: float) -> None:
    """One row of results/<phase>/runs.csv, in the columns forecast.py writes (no model, no forecast calls)."""
    cache.append_run(cfg["paths"]["results"], [meta["run_key"], split, cfg.get("_path"), meta["forecast_hash"], "cpu",
                                               "", "", started, datetime.now().isoformat(timespec="seconds"),
                                               f"{wall:.1f}", 0])
