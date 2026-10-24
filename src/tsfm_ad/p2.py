"""Phase 2: LANL forecasting, scores and evaluation (PLAN.md section 15, D140-D149). Phase 1 code paths are untouched;
this module reuses model_chronos2.load, its constant-row rule (D128) and quantile sorting (D119) and context.Fallback
(the Phase 1 FF interpretation). Scores, detection, red team and the MPS check are in p2_eval.py, which is not a
hashed source, so evaluation fixes never change a forecast cache key.

Runs (D144): `mv` (Chronos-2 per group, rolling), `mv-cov` (+ known-future covariates), `mv-ff` (ff-interp-block),
`mv-frozen` (time-of-day aligned clean reference, D145), `mv-dual` (mv vs mv-frozen, no inference) and the baselines
`lastvalue`, `seasonal-naive` and `robustz`. Every forecast is cached with all 21 quantiles under
cache/lanl/<model>/<run>@<hash8>/<part>.parquet (part = calib, seed<k>, redteam); scoring and evaluation read the
cache only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from tsfm_ad import context, inject, lanl
from tsfm_ad.baselines import MAD_TO_SD, Z_TAU
from tsfm_ad.cache import QCOLS, QUANTILE_LEVELS

SRC = Path(__file__).resolve().parent
HASHED = ("p2.py", "lanl.py", "inject.py", "model_chronos2.py", "context.py")
I05, I50, I95 = (QUANTILE_LEVELS.index(q) for q in (0.05, 0.50, 0.95))
TSFM_RUNS = {"mv": {"kind": "rolling", "cov": False}, "mv-cov": {"kind": "rolling", "cov": True},
             "mv-ff": {"kind": "ff", "cov": False}, "mv-frozen": {"kind": "frozen", "cov": False}}
BASELINES = ("lastvalue", "seasonal-naive", "robustz")


# ---- config and data ----

def load_cfg(path, smoke: bool = False) -> dict:
    cfg = yaml.safe_load(open(path))
    if smoke:
        s = cfg["smoke"]
        cfg["data"]["calib_days"], cfg["data"]["test_days"] = s["calib_days"], s["test_days"]
        cfg["inject"]["seeds"], cfg["inject"]["replicas"] = s["seeds"], s["replicas"]
        cfg["paths"]["results"] = str(Path(cfg["paths"]["results"]) / "smoke")
    return cfg


def span(cfg: dict, split: str) -> tuple[int, int]:
    a, b = cfg["data"][f"{split}_days"]
    return a * 1440, (b + 1) * 1440


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


class Data:
    """Raw series, fit statistics, groups, and the injected versions per seed."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        p = Path(cfg["paths"]["cache"]) / "prepared" / "raw.parquet"
        raw = pl.read_parquet(p)
        self.names = lanl.series_names(cfg)
        self.group_of = {s: g for g, ss in cfg["data"]["groups"].items() for s in ss}
        self.groups = [(g, [self.names.index(s) for s in ss]) for g, ss in cfg["data"]["groups"].items()]
        self.raw = {s: raw[s].to_numpy().astype(np.float64) for s in self.names}
        self.stats = lanl.fit_stats(raw, cfg)
        self.T = raw.height
        self.raw_sha = _sha(p)
        self.Z0 = self._z(self.raw)
        m = np.arange(self.T)
        self.cov = {"tod_sin": np.sin(2 * np.pi * (m % 1440) / 1440), "tod_cos": np.cos(2 * np.pi * (m % 1440) / 1440),
                    "day": m / 1440.0 / 58.0}

    def redteam_windows(self) -> list[tuple[int, int]]:
        """Minute ranges +- redteam.window_min around each red-team cluster (D147)."""
        return [(a - self.cfg["redteam"]["window_min"], b + self.cfg["redteam"]["window_min"] + 1)
                for a, b, _ in redteam_clusters(self.cfg)]

    def _z(self, raw: dict) -> np.ndarray:
        return lanl.transform(np.vstack([raw[s] for s in self.names]), [self.stats[s] for s in self.names])

    def seeded(self, seed: int):
        """(Z, labels (V, T), manifest, dropped) of one seed's injections in the test days."""
        lo, hi = span(self.cfg, "test")
        man, dropped = inject.schedule(self.cfg["inject"], seed, lo, hi, self.group_of, avoid=self.redteam_windows())
        inj, lab = inject.apply(self.raw, man, self.cfg["inject"])
        return self._z(inj), np.vstack([lab[s] for s in self.names]), man, dropped


# ---- cache keys ----

def model_tag(cfg: dict) -> str:
    return f"chronos2-{cfg['model']['chronos2']['revision'][:7]}-{cfg['model']['device']}"


def run_hash(cfg: dict, run: str, data: Data, extra=None) -> str:
    spec = TSFM_RUNS.get(run, {"kind": run, "cov": False})
    f = cfg["forecast"]
    payload = {"run": run, "spec": spec, "data": cfg["data"], "inject": cfg["inject"], "raw_sha": data.raw_sha,
               "forecast": {"H": f["H"], "cap": f["cap"], "batch": f["batch"] if spec["kind"] == "rolling" else 1,
                            "covariates": f["covariates"] if spec["cov"] else []},
               "sources": {n: _sha(SRC / n) for n in HASHED}, "extra": extra}
    if run not in BASELINES:
        m = cfg["model"]
        payload["model"] = {k: m["chronos2"][k] for k in ("repo", "revision", "package", "dtype")} | {
            "device": m["device"], "max_context": m["max_context"]}
    if spec["kind"] == "ff":
        payload["ff"] = cfg["ff"]
    if run in BASELINES:
        payload["baselines"] = cfg["baselines"]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def run_dir(cfg: dict, run: str, data: Data, extra=None) -> Path:
    model = "baseline" if run in BASELINES else model_tag(cfg)
    return Path(cfg["paths"]["cache"]) / model / f"{run}@{run_hash(cfg, run, data, extra)[:8]}"


# ---- frames ----

def _frame(names, idx, t0, origin, Q, Y, L) -> pl.DataFrame:
    """Rows for series idx over steps t0..t0+n-1 of one origin: Q (V, n, 21), Y and L (V, n)."""
    V, n = Q.shape[0], Q.shape[1]
    cols = {"series": np.repeat([names[i] for i in idx], n), "t": np.tile(np.arange(t0, t0 + n), V).astype(np.int32),
            "origin": np.full(V * n, origin, np.int32), "h": np.tile(np.arange(t0 - origin + 1, t0 - origin + n + 1),
                                                                      V).astype(np.int16)}
    flat = Q.reshape(V * n, -1).astype(np.float32)
    cols |= {q: flat[:, j] for j, q in enumerate(QCOLS)}
    cols |= {"y": Y.reshape(-1).astype(np.float32), "label": L.reshape(-1).astype(np.int8)}
    return pl.DataFrame(cols)


def _post(q, shift, stats) -> np.ndarray:
    """(V, 21, H) model output -> (V, H, 21): finite check, crossings sorted (D119), constant rows shifted (D128)."""
    q = q.permute(0, 2, 1).numpy().astype(np.float32) if hasattr(q, "permute") else np.asarray(q, np.float32)
    if not np.isfinite(q).all():
        raise ValueError("Chronos-2 returned non-finite quantiles")
    crossed = (np.diff(q, axis=-1) < 0).any(axis=-1)
    stats["forecasts"] += crossed.size
    stats["crossed"] += int(crossed.sum())
    if crossed.any():
        q = np.sort(q, axis=-1)
    return q + shift[:, None, None]


def _item(Zc, idx, o, cap, H, cov):
    from tsfm_ad import model_chronos2

    lo = max(0, o - cap)
    tgt, shift = model_chronos2._zero_constant_rows(Zc[idx, lo:o])
    item = {"target": tgt}
    if cov is not None:
        item["past_covariates"] = {k: v[lo:o].astype(np.float32) for k, v in cov.items()}
        item["future_covariates"] = {k: v[o:o + H].astype(np.float32) for k, v in cov.items()}
    return item, shift


def rolling(pipe, data: Data, Z, L, a: int, b: int, cfg: dict, cov: bool, stats: dict) -> pl.DataFrame:
    """Origins a, a + H, ... < b, every group, `batch` origins per call (items are independent: cross_learning off)."""
    H, cap, B = cfg["forecast"]["H"], cfg["forecast"]["cap"], cfg["forecast"]["batch"]
    cv = {k: data.cov[k] for k in cfg["forecast"]["covariates"]} if cov else None
    origins = list(range(a, b, H))
    parts = []
    for _, idx in data.groups:
        for i in range(0, len(origins), B):
            os_ = origins[i:i + B]
            items, shifts = zip(*(_item(Z, idx, o, cap, H, cv) for o in os_))
            t0 = time.time()
            out = pipe.predict(list(items), prediction_length=H, cross_learning=False, limit_prediction_length=True,
                               batch_size=len(items))
            stats["calls"] += 1
            stats["seconds"] += time.time() - t0
            for o, q, sh in zip(os_, out, shifts):
                n = min(H, b - o)
                Q = _post(q, sh, stats)[:, :n]
                parts.append(_frame(data.names, idx, o, o, Q, Z[idx, o:o + n], L[idx, o:o + n]))
    return pl.concat(parts).sort("series", "t")


def ff_tau(calib_mv: pl.DataFrame, names, pct: float) -> np.ndarray:
    tau = context.ff_thresholds(calib_mv.rename({"y": "y_true", "series": "channel"}), pct)
    return np.array([tau[s] for s in names])


def ff_run(pipe, data: Data, Z, L, a: int, b: int, cfg: dict, tau: np.ndarray, stats: dict):
    """ff-interp-block origin by origin over all groups: substituted q50 enter later contexts (Phase 1 D24, D44)."""
    H, cap = cfg["forecast"]["H"], cfg["forecast"]["cap"]
    Zc = Z.copy()
    hook = context.Fallback(tau, k=cfg["ff"]["k"], max_duration=cfg["ff"]["max_duration"])
    parts, V = [], len(data.names)
    for o in range(a, b, H):
        n = min(H, b - o)
        Q = np.empty((V, n, len(QCOLS)), np.float32)
        for _, idx in data.groups:
            item, sh = _item(Zc, idx, o, cap, H, None)
            t0 = time.time()
            out = pipe.predict([item], prediction_length=H, cross_learning=False, limit_prediction_length=True)
            stats["calls"] += 1
            stats["seconds"] += time.time() - t0
            Q[idx] = _post(out[0], sh, stats)[:, :n]
        mask = hook(o, Q[:, :, I50], Z[:, o:o + n])
        sub = Zc[:, o:o + n]
        sub[mask] = Q[:, :, I50][mask]
        Zc[:, o:o + n] = sub
        f = _frame(data.names, list(range(V)), o, o, Q, Z[:, o:o + n], L[:, o:o + n])
        parts.append(f.with_columns(substituted=pl.Series(mask.reshape(-1))))
    eps = context.episodes_frame("lanl", hook.episodes(), data.names)
    return pl.concat(parts).sort("series", "t"), eps


def frozen_refs(pipe, data: Data, cfg: dict, stats: dict) -> np.ndarray:
    """(48, V, H, 21): for each 30-min time-of-day slot k, the forecast from the clean fit minutes that end at slot k
    of the last fit day (D145). Fit days are never injected."""
    H, cap = cfg["forecast"]["H"], cfg["forecast"]["cap"]
    last = cfg["data"]["fit_days"][1] * 1440
    V = len(data.names)
    R = np.empty((1440 // H, V, H, len(QCOLS)), np.float32)
    for _, idx in data.groups:
        ends = [last + k * H for k in range(1440 // H)]
        items, shifts = zip(*(_item(data.Z0, idx, e, cap, H, None) for e in ends))
        out = pipe.predict(list(items), prediction_length=H, cross_learning=False, limit_prediction_length=True,
                           batch_size=len(items))
        stats["calls"] += 1
        for k, (q, sh) in enumerate(zip(out, shifts)):
            R[k][idx] = _post(q, sh, stats)
    return R


def frozen_frame(R, data: Data, Z, L, a: int, b: int, H: int) -> pl.DataFrame:
    parts, V = [], len(data.names)
    for o in range(a, b, H):
        n = min(H, b - o)
        parts.append(_frame(data.names, list(range(V)), o, o, R[(o % 1440) // H][:, :n], Z[:, o:o + n],
                            L[:, o:o + n]))
    return pl.concat(parts).sort("series", "t")


# ---- baselines (D144; Phase 1 definitions on the minute grid) ----

def baseline_frame(name: str, data: Data, Z, L, a: int, b: int, cfg: dict) -> pl.DataFrame:
    H, V = cfg["forecast"]["H"], len(data.names)
    lo, hi = span(cfg, "fit")
    X = data.Z0[:, lo:hi]
    levels = np.array(QUANTILE_LEVELS)
    if name == "lastvalue":
        D = np.stack([np.quantile(X[:, h:] - X[:, :-h], levels, axis=1).T for h in range(1, H + 1)], axis=1)
    elif name == "seasonal-naive":
        lag = cfg["baselines"]["seasonal_lag"]
        D = np.quantile(X[:, lag:] - X[:, :-lag], levels, axis=1).T          # (V, 21)
    parts = []
    for o in range(a, b, H):
        n = min(H, b - o)
        if name == "lastvalue":
            Q = Z[:, o - 1][:, None, None] + D[:, :n]
        elif name == "seasonal-naive":
            lag = cfg["baselines"]["seasonal_lag"]
            Q = Z[:, o - lag:o - lag + n][:, :, None] + D[:, None, :]
        else:
            w = Z[:, o - cfg["baselines"]["robustz_window"]:o]
            m = np.median(w, axis=1)
            mad = np.median(np.abs(w - m[:, None]), axis=1)
            Q = np.repeat((m[:, None] + Z_TAU[None, :] * MAD_TO_SD * mad[:, None])[:, None, :], n, axis=1)
        parts.append(_frame(data.names, list(range(V)), o, o, Q, Z[:, o:o + n], L[:, o:o + n]))
    return pl.concat(parts).sort("series", "t")


# ---- forecast stage ----

def _write(df: pl.DataFrame, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.write_parquet(tmp)
    tmp.replace(path)
    (path.parent / "meta.json").write_text(json.dumps(meta, indent=1, default=str))


def _log_run(cfg, run, part, seconds, calls, extra=None) -> None:
    out = Path(cfg["paths"]["results"]) / "runs.csv"
    row = pl.DataFrame([{"run": run, "part": part, "device": cfg["model"]["device"], "seconds": round(seconds, 1),
                         "calls": calls, "finished": time.strftime("%Y-%m-%dT%H:%M:%S"), **(extra or {})}])
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        row = pl.concat([pl.read_csv(out).filter(~((pl.col("run") == run) & (pl.col("part") == part))), row],
                        how="diagonal_relaxed")
    row.write_csv(out)


def parts(cfg: dict) -> list[str]:
    return ["calib"] + [f"seed{s}" for s in cfg["inject"]["seeds"]]


def _inputs(data: Data, part: str, cache: dict):
    if part not in cache:
        if part == "calib":
            cache[part] = (data.Z0, np.zeros_like(data.Z0, np.int8), None, [])
        else:
            cache[part] = data.seeded(int(part[4:]))
    return cache[part]


def forecast(cfg: dict, runs=None) -> None:
    """Every TSFM run and baseline over calib and each seed's test days; cached parts are skipped."""
    from tsfm_ad import model_chronos2

    data, inputs = Data(cfg), {}
    out = Path(cfg["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    mans = [_inputs(data, f"seed{s}", inputs)[2] for s in cfg["inject"]["seeds"]]
    pl.concat(mans).write_csv(out / "injections.csv")
    dropped = [d for s in cfg["inject"]["seeds"] for d in _inputs(data, f"seed{s}", inputs)[3]]
    (out / "injections_dropped.txt").write_text("\n".join(dropped) + ("\n" if dropped else ""))
    runs = runs or [*TSFM_RUNS, *BASELINES]
    pipe = None
    for run in runs:
        spec = TSFM_RUNS.get(run, {"kind": run})
        tau = None
        if spec["kind"] == "ff":
            tau = ff_tau(read(cfg, "mv", "calib", data), data.names, cfg["ff"]["pct"])
        extra = {"ff_tau_sha256": hashlib.sha256(tau.tobytes()).hexdigest()} if tau is not None else None
        d = run_dir(cfg, run, data, extra)
        refs = None
        for part in parts(cfg):
            path = d / f"{part}.parquet"
            if path.exists():
                print(f"p2 {run} {part}: cached ({d.name})", flush=True)
                continue
            Z, L, _, _ = _inputs(data, part, inputs)
            a, b = span(cfg, "calib" if part == "calib" else "test")
            stats = {"forecasts": 0, "crossed": 0, "calls": 0, "seconds": 0.0}
            t0 = time.time()
            if run in BASELINES:
                df = baseline_frame(run, data, Z, L, a, b, cfg)
            else:
                if pipe is None:
                    pipe = model_chronos2.load(cfg["model"], cfg["paths"]["hf_cache"])
                if spec["kind"] == "rolling":
                    df = rolling(pipe, data, Z, L, a, b, cfg, spec["cov"], stats)
                elif spec["kind"] == "frozen":
                    refs = frozen_refs(pipe, data, cfg, stats) if refs is None else refs
                    df = frozen_frame(refs, data, Z, L, a, b, cfg["forecast"]["H"])
                else:
                    df, eps = ff_run(pipe, data, Z, L, a, b, cfg, tau, stats)
            _write(df, path, {"run": run, "hash": run_hash(cfg, run, data, extra), "part": part})
            if spec["kind"] == "ff":
                eps.with_columns(part=pl.lit(part)).write_csv(d / f"{part}_episodes.csv")
            _log_run(cfg, run, part, time.time() - t0, stats["calls"],
                     {"forecasts": stats["forecasts"], "crossed": stats["crossed"]})
            print(f"p2 {run} {part}: {df.height} rows in {time.time() - t0:.0f} s"
                  + (f", crossings sorted {stats['crossed']} of {stats['forecasts']}" if stats["forecasts"] else ""),
                  flush=True)


def read(cfg: dict, run: str, part: str, data: Data | None = None) -> pl.DataFrame:
    data = data or Data(cfg)
    extra = None
    if TSFM_RUNS.get(run, {}).get("kind") == "ff":
        tau = ff_tau(read(cfg, "mv", "calib", data), data.names, cfg["ff"]["pct"])
        extra = {"ff_tau_sha256": hashlib.sha256(tau.tobytes()).hexdigest()}
    path = run_dir(cfg, run, data, extra) / f"{part}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run the p2 forecast stage")
    return pl.read_parquet(path)


# ---- red-team clusters (D146, D147) ----

def redteam_clusters(cfg: dict) -> list[tuple[int, int, int]]:
    """(first minute, last minute, events) of the red-team events, merged when less than window_min apart."""
    w = cfg["redteam"]["window_min"]
    rt = pl.read_csv(Path(cfg["paths"]["lanl"]) / "redteam.txt.gz", has_header=False,
                     new_columns=["time", "user", "src", "dst"])
    mins = np.sort((rt["time"].to_numpy() - 1) // 60)
    out, cur = [], [int(mins[0]), int(mins[0]), 1]
    for m in mins[1:]:
        if m - cur[1] <= w:
            cur[1], cur[2] = int(m), cur[2] + 1
        else:
            out.append(tuple(cur))
            cur = [int(m), int(m), 1]
    out.append(tuple(cur))
    return [c for c in out if c[0] < cfg["data"]["minutes"]]
