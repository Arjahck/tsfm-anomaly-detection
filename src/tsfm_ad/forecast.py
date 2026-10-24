"""TSFM inference into the forecast cache: rolling (in-file or prepend warm-up), Forecast Fallback, frozen
reference and the cf-onset counterfactual. PLAN.md 2.3-2.5, 6, 6.1, 8, 14, D13-D15, D46, D58, D117-D121.

One predict interface for both models, dispatched by `model.name`: `chronos2` (Phase 1, model_chronos2.py) and
`timestral` (paused for licence reasons: refused unless TSFM_ALLOW_TIMESTRAL=1, CLAUDE.md).
`setup` arguments are a setup's `list[data.Group]`; `fcfg` is `forecast_params(cfg)`.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import numpy as np
import polars as pl

from tsfm_ad import cache, context, data
from tsfm_ad.cache import QCOLS
from tsfm_ad.config import TSFM_MODELS, resolve_setup, run_key, steps

MEDIAN = QCOLS.index("q50")
SPLITS_NEEDED = {"rolling": ["calib", "test"], "ff": ["calib", "test"], "frozen": ["ref"], "cf-onset": ["test"]}


TIMESTRAL_PAUSED = ("Timestral is paused (licence pause, see CLAUDE.md): model.name timestral is refused. Phase 1 "
                    "runs on chronos2 (configs/base.yaml). Set TSFM_ALLOW_TIMESTRAL=1 only after Arthur confirms "
                    "Mistral's written permission.")


def load_forecaster(model_cfg: dict, cache_dir="cache/hf"):
    """The model of `model.name` at its pinned revision: chronos2 (model_chronos2.load), or timestral (paused:
    only with TSFM_ALLOW_TIMESTRAL=1; on mps the UNOFFICIAL shim is installed first, D15)."""
    if model_cfg["name"] == "chronos2":
        from tsfm_ad import model_chronos2

        return model_chronos2.load(model_cfg, cache_dir)
    if model_cfg["name"] != "timestral":
        raise ValueError(f"model.name {model_cfg['name']!r} is not a forecasting model {TSFM_MODELS}")
    if os.environ.get("TSFM_ALLOW_TIMESTRAL") != "1":
        raise RuntimeError(TIMESTRAL_PAUSED)
    import torch
    from timestral import TimestralForecaster

    torch.set_num_threads(model_cfg.get("cpu_threads", 4))
    if model_cfg["device"] == "mps":
        from tsfm_ad import mps_shim

        mps_shim.install()
    size = model_cfg["size"]
    kw = {"revision": model_cfg["revisions"][size], "device": model_cfg["device"],
          "max_context": model_cfg["max_context"], "cache_dir": str(cache_dir)}
    try:   # the pinned weights are usually in cache/hf already: no network call then
        return TimestralForecaster.from_pretrained(model_cfg["repo_prefix"] + size, local_files_only=True, **kw)
    except (OSError, ValueError):
        return TimestralForecaster.from_pretrained(model_cfg["repo_prefix"] + size, **kw)


def forecast_params(cfg: dict) -> dict:
    """H, W (steps), cap, warm-up, the model name, the two Timestral flags (unused by chronos2), and whether the
    setup forecasts groups jointly."""
    f = cfg["forecast"]
    if f["cap"] > cfg["model"]["max_context"]:
        raise ValueError(f"cap {f['cap']} exceeds model.max_context {cfg['model']['max_context']}")
    mode = cfg["channels"]["setups"][resolve_setup(cfg)]["mode"]
    return {"H": f["H"], "W": steps(cfg, f["W_s"]), "cap": f["cap"], "warmup": f["warmup"],
            "model": cfg["model"]["name"], "symmetric_averaging": f.get("symmetric_averaging"),
            "clip_nonnegative": f.get("clip_nonnegative"), "multivariate": mode == "multivariate"}


def origins(L: int, W: int, H: int) -> np.ndarray:
    """Forecast origins W, W + H, ... < L; window [o, o + H), context ends at o - 1."""
    return np.arange(W, L, H)


def predict(fc, groups, ctx_slices, H: int, flags: dict, log=None) -> np.ndarray:
    """Quantiles (sum of targets, H, 21) for one origin: one call per group (never merged, PLAN 2.1).

    ctx_slices[i] = (targets (V, T), covariates (C, T) or None) of groups[i]. Univariate: the V targets are B
    independent series. Multivariate: one joint series with past-only covariates. `flags["model"]` picks the
    backend (default timestral, the stub path of the tests). `log(T, rows, seconds, crossed, forecasts, const_rows)`
    is called per model call: rows = target + covariate rows; for chronos2 `crossed` of the `forecasts` = targets x H
    (channel, h) forecasts had crossing quantiles and were sorted (D119), and `const_rows` rows were constant over
    the context (D128); timestral logs only the first three.
    """
    from tsfm_ad import model_chronos2

    out = []
    for g, (tgt, cov) in zip(groups, ctx_slices):
        if tgt.shape[1] < 1 or not np.isfinite(tgt).all() or (cov is not None and not np.isfinite(cov).all()):
            raise ValueError(f"group {g.name}: empty or non-finite context (shape {tgt.shape})")
        t0 = time.perf_counter()
        if flags.get("model", "timestral") == "chronos2":
            before = dict(model_chronos2.STATS)
            q = model_chronos2.predict_group(fc, tgt, cov, H, flags["multivariate"])
            if log is not None:
                log(tgt.shape[1], tgt.shape[0] + (0 if cov is None else len(cov)), time.perf_counter() - t0,
                    *(model_chronos2.STATS[k] - before[k] for k in ("crossed", "forecasts", "const_rows")))
            out.append(q)
            continue
        kw = {"symmetric_averaging": flags["symmetric_averaging"], "clip_nonnegative": flags["clip_nonnegative"]}
        if flags["multivariate"]:
            past = cov[None] if cov is not None and len(cov) else None
            q = fc.forecast(np.ascontiguousarray(tgt)[None], H, past_covariates=past, **kw).quantiles[0]
        else:
            if cov is not None and len(cov):
                raise ValueError("univariate setups take no covariates")
            q = fc.forecast(np.ascontiguousarray(tgt), H, **kw).quantiles[:, 0]
        q = q.cpu().numpy()
        if log is not None:
            log(tgt.shape[1], tgt.shape[0] + (0 if cov is None else len(cov)), time.perf_counter() - t0)
        out.append(q)
    return np.concatenate(out).astype(np.float32, copy=False)


def _rows(channels: list[str], setup) -> list[tuple[list[int], list[int]]]:
    idx = {c: i for i, c in enumerate(channels)}
    return [([idx[c] for c in g.targets], [idx[c] for c in g.covariates]) for g in setup]


def _frame(seg, names, t, Q, origin, ctx_len, sub=None) -> pl.DataFrame:
    """Long cache rows for C channels x steps t. Q (C, n, 21); origin, ctx_len (n,); sub (C, n). y_true from seg."""
    C, n = len(names), len(t)
    d = {"file": pl.repeat(seg.name, C * n, dtype=pl.String, eager=True),
         "channel": pl.Series(names, dtype=pl.String).gather(np.repeat(np.arange(C), n)),
         "t": np.tile(t, C), "time": np.tile(seg.time[t], C), "origin": np.tile(origin, C),
         "h": np.tile(t - origin + 1, C), "ctx_len": np.tile(ctx_len, C)}
    q = Q.reshape(C * n, len(QCOLS))
    d.update({col: q[:, i] for i, col in enumerate(QCOLS)})
    d["y_true"] = seg.rows(names)[:, t].reshape(-1)
    d["label"] = np.tile(seg.labels[t], C)
    d["substituted"] = np.zeros(C * n, bool) if sub is None else sub.reshape(-1)
    return pl.DataFrame(d)


def rolling(fc, seg, setup, fcfg, hook=None, prefix=None, log=None) -> pl.DataFrame:
    """Rolling forecast of one file (D58). Z_obs (read-only) is the prepared data, the only source of y and of
    covariates. Z_ctx, a per-file copy of the targets, is the only array target contexts are sliced from. After
    each window, `hook(o, q50, y) -> mask` and Z_ctx[:, o:o+H][mask] = q50[mask]. `prefix` (all channels, P steps)
    is the prepend warm-up; it shifts the contexts, not the scored steps t >= W.
    """
    H, W, cap, L = fcfg["H"], fcfg["W"], fcfg["cap"], len(seg)
    P = 0 if prefix is None else prefix.shape[1]
    Z_obs = seg.Z.view() if prefix is None else np.concatenate([prefix, seg.Z], axis=1)
    Z_obs.flags.writeable = False
    names = [c for g in setup for c in g.targets]
    rows = _rows(seg.channels, setup)
    tgt_all = [i for r, _ in rows for i in r]
    Z_ctx = Z_obs[tgt_all].copy()
    spans, pos = [], 0
    for r, _ in rows:
        spans.append(slice(pos, pos + len(r)))
        pos += len(r)
    Y = Z_obs[tgt_all, P:]
    Q = np.full((len(names), L, len(QCOLS)), np.nan, np.float32)
    origin, ctx_len = np.full(L, -1, np.int64), np.zeros(L, np.int64)
    sub = np.zeros((len(names), L), bool)
    os_ = origins(L, W, H)
    for i, o in enumerate(os_):
        p, n = P + o, min(H, L - o)
        lo = max(0, p - cap)
        slices = [(Z_ctx[s, lo:p], Z_obs[c, lo:p] if c else None) for s, (_, c) in zip(spans, rows)]
        q = predict(fc, setup, slices, H, fcfg, log)[:, :n]
        Q[:, o:o + n], origin[o:o + n], ctx_len[o:o + n] = q, o, p - lo
        if hook is not None:
            q50 = q[:, :, MEDIAN]
            mask = hook(o, q50, Y[:, o:o + n])
            Z_ctx[:, p:p + n][mask] = q50[mask]
            sub[:, o:o + n] = mask
        if i and i % 1000 == 0:
            print(f"    {seg.name}: {i} of {len(os_)} origins", flush=True)
    t = np.arange(W, L)
    return _frame(seg, names, t, Q[:, W:], origin[W:], ctx_len[W:], sub[:, W:])


def cf_onset(fc, seg, setup, fcfg, attacks: pl.DataFrame, N: int, log=None) -> pl.DataFrame:
    """Clean-context counterfactual (D46): per attack of this segment, one forecast from the onset s with the
    in-file context [max(0, s - cap), s) and horizon L_attack + N (cut at the file end). Diagnostic only."""
    names = [c for g in setup for c in g.targets]
    rows, L = _rows(seg.channels, setup), len(seg)
    Z_obs = seg.Z.view()
    Z_obs.flags.writeable = False
    parts = []
    for a in attacks.filter(pl.col("segment") == seg.name).sort("start_idx").iter_rows(named=True):
        s = a["start_idx"]
        n, lo = min(a["n_steps"] + N, L - s), max(0, s - fcfg["cap"])
        slices = [(Z_obs[r, lo:s], Z_obs[c, lo:s] if c else None) for r, c in rows]
        q = predict(fc, setup, slices, n, fcfg, log)
        parts.append(_frame(seg, names, np.arange(s, s + n), q, np.full(n, s), np.full(n, s - lo)))
    if not parts:
        return _frame(seg, names, np.arange(0), np.zeros((len(names), 0, len(QCOLS)), np.float32),
                      np.arange(0), np.arange(0))
    return pl.concat(parts)


def estimate_runtime(fc, seg, setup, fcfg, segs=None, prefix=None) -> float:
    """Times 3 real calls on `seg` (shortest, median and longest context of the run), interpolates the cost over
    every origin of `segs` (default [seg]), prints and returns the estimated seconds."""
    segs = segs or [seg]
    P = 0 if prefix is None else prefix.shape[1]
    Ts = np.concatenate([np.minimum(fcfg["cap"], P + origins(len(s), fcfg["W"], fcfg["H"])) for s in segs])
    if not len(Ts):
        return 0.0
    full = seg.Z if prefix is None else np.concatenate([prefix, seg.Z], axis=1)
    rows = _rows(seg.channels, setup)

    def call(T):
        t0 = time.perf_counter()
        predict(fc, setup, [(full[r, :T], full[c, :T] if c else None) for r, c in rows], fcfg["H"], fcfg)
        return time.perf_counter() - t0

    probe = sorted({int(Ts.min()), int(np.median(Ts)), int(Ts.max())})
    call(probe[0])                                    # warm-up, not timed (first MPS call compiles kernels)
    secs = [call(T) for T in probe]
    est = float(np.interp(Ts, probe, secs).sum())
    print(f"  estimate: {len(Ts)} origins, about {est / 60:.1f} min; timed T={probe}: "
          f"{', '.join(f'{s:.3f}' for s in secs)} s per origin", flush=True)
    return est


def splits_for(cfg: dict, split: str = "all") -> list[str]:
    """Splits a variant forecasts: rolling and ff calib + test (+ calib2 if a calib source), frozen ref,
    cf-onset test, dual none. An explicit split must be one of them (calib2 always allowed for rolling/ff)."""
    kind = cfg["variant"]["kind"]
    need = list(SPLITS_NEEDED.get(kind, []))
    extra = ["calib2"] if kind in ("rolling", "ff") else []
    if extra and "calib2" in cfg["score"]["calib_sources"]:
        need.insert(1, "calib2")
    if split == "all":
        return need
    if split not in need + extra:
        raise ValueError(f"variant {kind} does not forecast split {split!r}; it needs {need}")
    return [split]


def _prepend_prefix(cfg: dict, channels: list[str]) -> np.ndarray:
    """The last `cap` steps of train3 (ending 2020-08-10 10:59:50 at 10 s), PLAN.md section 5."""
    src = data.load_segment(cfg, "train3")
    if src.channels != channels:
        raise ValueError("train3 and the forecast segment hold different channels")
    return src.Z[:, -cfg["forecast"]["cap"]:]


def _append_run(cfg, split, meta, started, wall, n_calls) -> None:
    m = cfg["model"]
    if m["name"] == "chronos2":
        code, rev = m["chronos2"]["package"], m["chronos2"]["revision"]
    else:
        code, rev = m["timestral_commit"], m["revisions"][m["size"]]
    cache.append_run(cfg["paths"]["results"], [meta["run_key"], split, cfg.get("_path"), meta["forecast_hash"],
                                                m["device"], code, rev, started,
                                                datetime.now().isoformat(timespec="seconds"), f"{wall:.1f}", n_calls])


def run_forecast(cfg: dict, split: str = "all") -> None:
    """Forecast every file of the variant's splits into the cache; files whose parquet exists are skipped."""
    kind = cfg["variant"]["kind"]
    if kind == "dual":
        print("dual needs no inference: it is scored from the rolling and frozen caches")
        return
    if cfg["model"]["name"] not in TSFM_MODELS:
        raise ValueError(f"model.name {cfg['model']['name']!r} is not a forecasting model: use `tsfm-ad baselines`")
    setup = data.setup_groups(cfg, resolve_setup(cfg))
    fcfg = forecast_params(cfg)
    tau = context.ff_tau(cfg) if kind == "ff" else None
    extra = context.ff_extra(cfg, tau)
    rdir, meta = cache.run_dir(cfg, extra=extra), cache.meta(cfg, extra=extra)
    jobs = [(sp, seg) for sp in splits_for(cfg, split) for seg in data.load_split(cfg, sp)]
    todo = [(sp, seg) for sp, seg in jobs if not (rdir / sp / f"{seg.name}.parquet").exists()]
    print(f"forecast {run_key(cfg)} -> {rdir}: {len(todo)} of {len(jobs)} files to run", flush=True)
    if not todo:
        return
    fc = load_forecaster(cfg["model"], cfg["paths"]["hf_cache"])
    names = [c for g in setup for c in g.targets]
    prefix = None
    if fcfg["warmup"] == "prepend" and kind in ("rolling", "ff"):
        prefix = _prepend_prefix(cfg, todo[0][1].channels)
    if kind in ("rolling", "ff"):
        segs = [seg for _, seg in todo]
        estimate_runtime(fc, max(segs, key=len), setup, fcfg, segs=segs, prefix=prefix)
    if kind == "ff":
        ff = cfg["variant"]["ff"]
        hook = context.Fallback([tau[c] for c in names], k=ff["k"], max_duration=ff["max_duration"],
                                scope=ff["scope"])
    attacks = data.load_attacks(cfg) if kind == "cf-onset" else None
    for sp in dict.fromkeys(sp for sp, _ in todo):
        # D116: a file's calls are logged only once its parquet is written, and runs.csv gets a row for the files
        # this invocation wrote even when a later file fails, so a resumed run is neither double counted nor lost.
        started, wall, n_calls, n_files = datetime.now().isoformat(timespec="seconds"), 0.0, 0, 0
        try:
            for seg in [s for p, s in todo if p == sp]:
                t0, path, calls = time.time(), rdir / sp / f"{seg.name}.parquet", []
                log = lambda *call: calls.append(call)  # noqa: E731
                if kind == "rolling":
                    df = rolling(fc, seg, setup, fcfg, prefix=prefix, log=log)
                elif kind == "ff":
                    hook.reset()
                    df = rolling(fc, seg, setup, fcfg, hook=hook, prefix=prefix, log=log)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_name(f".{seg.name}.ff_episodes.csv.tmp")
                    context.episodes_frame(seg.name, hook.episodes(), names).write_csv(tmp)
                    tmp.replace(path.with_name(f"{seg.name}.ff_episodes.csv"))
                elif kind == "cf-onset":
                    df = cf_onset(fc, seg, setup, fcfg, attacks, steps(cfg, cfg["metrics"]["N_onset_s"]), log=log)
                else:
                    df = context.frozen_forecast(fc, seg, setup, fcfg, log=log)
                cache.write(df, path, meta)
                for call in calls:
                    cache.log_call(rdir / f"calls_{sp}.csv", *call)
                wall, n_calls, n_files = wall + time.time() - t0, n_calls + len(calls), n_files + 1
                note = ""
                if calls and len(calls[0]) == 6:   # chronos2: sorted crossings (D119), zeroed constant rows (D128)
                    note = (f"; quantile crossings sorted in {sum(c[3] for c in calls)} of "
                            f"{sum(c[4] for c in calls)} (channel, h) forecasts; {sum(c[5] for c in calls)} "
                            "constant rows zeroed")
                print(f"  {sp}/{seg.name}: {df.height} rows in {time.time() - t0:.1f} s{note}", flush=True)
        finally:
            if n_files:
                _append_run(cfg, sp, meta, started, wall, n_calls)
