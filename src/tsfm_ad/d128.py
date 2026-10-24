"""The size of the D128 constant-row guard (PLAN.md 14.5): how far it moves the Chronos-2 forecasts of a run
against the same calls without the guard (the model as shipped), on the run's own device (CPU for the headline
runs, D121). Diagnostic only: it reads prepared data, calls the model and writes two results CSVs; it never reads
or writes the forecast cache.

The guard changes only calls whose context holds a constant row; every other call goes to the model unchanged,
so its forecast is the raw one bit for bit and counts as moved by 0. For each call with a constant row the adapter
forecast (`model_chronos2.predict_group`) is compared with the same function with the guard switched off
(`raw_group`). Contexts are rebuilt exactly as forecast.rolling (in-file warm-up, no FF), forecast.cf_onset and
context.frozen_forecast build them; FF and prepend runs are not measured (their contexts are the rolling ones with
substituted targets or a train3 prefix).

Outputs in `paths.results`: `d128_effect.csv` (one row per run key, forecast hash and split) and
`d128_effect_channels.csv` (the same per target channel with a re-run forecast). `forecasts_rerun` counts the
(channel, step) forecasts the guard can change: every target of a multivariate call with a constant row, only the
constant rows of a univariate call (run as a batch of their own; rows are independent, PLAN.md 14.4). Shares are
over all `values` = forecasts x 21 of the split. `dq` = |adapter - raw| over all 21 levels in fit-z;
`max_dq_q05_q50_q95` the same over the levels the band score and FF read (the outer levels of Chronos-2 can reach
1e5 z or more on a near-constant context, with or without the guard); `dq_band` = dq / (adapter q95 - q05 + eps);
`dband` = |band score adapter - band score raw| at the observed value (D17; empty for frozen, which has no single
observed window; `share_dband_gt_1` is over all forecasts of the split).
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad import data, forecast, model_chronos2
from tsfm_ad.cache import QCOLS, run_dir
from tsfm_ad.config import resolve_setup, run_key, steps
from tsfm_ad.score import band

Q05, Q95 = QCOLS.index("q05"), QCOLS.index("q95")
BAND_LV = [QCOLS.index(q) for q in ("q05", "q50", "q95")]   # what the band score and FF read (D17, D24)
# PLAN.md 14.8 latency: seconds per row-step and per call, for the printed estimate only
LATENCY = {"cpu": (11.2e-6, 0.01), "mps": (6.2e-6, 0.018)}
SUMMARY = "d128_effect.csv"
CHANNELS = "d128_effect_channels.csv"


@contextmanager
def _guard_off():
    """model_chronos2 with `_zero_constant_rows` replaced by the identity: the adapter path minus D128 only."""
    keep = model_chronos2._zero_constant_rows
    model_chronos2._zero_constant_rows = lambda x: (np.ascontiguousarray(x, dtype=np.float32),
                                                    np.zeros(len(x), np.float32))
    try:
        yield
    finally:
        model_chronos2._zero_constant_rows = keep


def raw_group(pipe, tgt, cov, H: int, multivariate: bool) -> np.ndarray:
    """`model_chronos2.predict_group` without the constant-row guard (crossings still sorted, D119)."""
    with _guard_off():
        return model_chronos2.predict_group(pipe, tgt, cov, H, multivariate)


def has_constant_row(*xs) -> bool:
    """The adapter's own test (model_chronos2._zero_constant_rows): a row equal to its first value everywhere."""
    return any(x is not None and len(x) and bool((x == x[:, :1]).all(axis=1).any()) for x in xs)


def contexts(seg, kind: str, fcfg: dict, attacks=None, N: int = 0):
    """(origin, context start lo, context end p, horizon n) of every call of `kind` on `seg`, as forecast.rolling
    (in-file warm-up), forecast.cf_onset and context.frozen_forecast slice them."""
    H, W, cap, L = fcfg["H"], fcfg["W"], fcfg["cap"], len(seg)
    if kind == "rolling":
        for o in forecast.origins(L, W, H):
            yield int(o), max(0, int(o) - cap), int(o), min(H, L - int(o))
    elif kind == "cf-onset":
        for a in attacks.filter(pl.col("segment") == seg.name).sort("start_idx").iter_rows(named=True):
            s = a["start_idx"]
            yield s, max(0, s - cap), s, min(a["n_steps"] + N, L - s)
    elif kind == "frozen":
        yield L, max(0, L - cap), L, H
    else:
        raise ValueError(f"the D128 effect is measured for rolling, cf-onset and frozen, not {kind!r}")


def calls(segs, setup, kind: str, fcfg: dict, attacks=None, N: int = 0):
    """Every model call of a run on `segs`, in the order the forecast code makes them: (segment, origin, n, group,
    targets (V, T), covariates (C, T) or None, observed targets (V, n) or None for frozen, horizon passed)."""
    for seg in segs:
        arrays = [(g, seg.rows(g.targets), seg.rows(g.covariates) if g.covariates else None) for g in setup]
        for o, lo, p, n in contexts(seg, kind, fcfg, attacks, N):
            for g, Xt, Xc in arrays:
                y = None if kind == "frozen" else Xt[:, p:p + n]
                yield (seg.name, o, n, g, Xt[:, lo:p], None if Xc is None else Xc[:, lo:p], y,
                       n if kind == "cf-onset" else fcfg["H"])


def run_calls(cfg: dict, segs):
    """`calls` of the run `cfg` (rolling with in-file warm-up, cf-onset or frozen)."""
    kind, fcfg = cfg["variant"]["kind"], forecast.forecast_params(cfg)
    if kind == "rolling" and fcfg["warmup"] != "in_file":
        raise ValueError("the D128 effect is measured for in-file warm-up only (prepend contexts differ)")
    setup = data.setup_groups(cfg, resolve_setup(cfg))
    attacks = data.load_attacks(cfg) if kind == "cf-onset" else None
    N = steps(cfg, cfg["metrics"]["N_onset_s"]) if kind == "cf-onset" else 0
    return calls(segs, setup, kind, fcfg, attacks, N)


def changed_part(g, tgt, cov, y, multivariate: bool):
    """What the guard can change in one call: None without a constant row; for a multivariate call the whole call
    (its rows interact); for a univariate call only its constant rows, run as a batch of their own (rows are
    independent, PLAN.md 14.4, so every other row is bit-identical with and without the guard). Returns
    (target names, targets, covariates, observed targets)."""
    if not has_constant_row(tgt, cov):
        return None
    if multivariate:
        return g.targets, tgt, cov, y
    keep = (tgt == tgt[:, :1]).all(axis=1)
    return [c for c, k in zip(g.targets, keep) if k], tgt[keep], None, None if y is None else y[keep]


def measure(pipe, cfg: dict, split: str, segs, eps: float):
    """(summary row, per-channel rows) of one split. Calls without a constant row are counted, not run."""
    mv = forecast.forecast_params(cfg)["multivariate"]
    have_y = cfg["variant"]["kind"] != "frozen"
    names = [c for g in data.setup_groups(cfg, resolve_setup(cfg)) for c in g.targets]
    n_ctx = n_hit = n_fc = n_moved = 0
    top = {"dq": (0.0, "", "", -1), "dq_lv": (0.0, "", "", -1), "dq_band": (0.0, "", "", -1)}
    gt = {0.01: 0, 0.1: 0, 1.0: 0}
    dband_max, dband_gt1 = 0.0, 0
    ch = {c: {"moved": 0, "dq": 0.0, "dq_lv": 0.0, "gt01": 0, "dq_band": 0.0, "dband": 0.0} for c in names}
    for file, o, n, g, tgt, cov, y, Hc in run_calls(cfg, segs):
        n_ctx, n_fc = n_ctx + 1, n_fc + len(g.targets) * n
        part = changed_part(g, tgt, cov, y, mv)
        if part is None:
            continue
        targets, tgt, cov, y = part
        n_hit, n_moved = n_hit + 1, n_moved + len(targets) * n
        qa = model_chronos2.predict_group(pipe, tgt, cov, Hc, mv)[:, :n]
        qr = raw_group(pipe, tgt, cov, Hc, mv)[:, :n]
        dq = np.abs(qa.astype(np.float64) - qr)                                 # (V, n, 21)
        dqb = dq / (qa[..., Q95].astype(np.float64) - qa[..., Q05] + eps)[..., None]
        for th in gt:
            gt[th] += int((dq > th).sum())
        for key, arr in (("dq", dq), ("dq_lv", dq[..., BAND_LV]), ("dq_band", dqb)):
            if arr.max() > top[key][0]:
                v = int(np.unravel_index(int(arr.argmax()), arr.shape)[0])
                top[key] = (float(arr.max()), targets[v], file, o)
        db = None
        if have_y:
            db = np.abs(band(y, qa[..., Q05], qa[..., Q95], eps) - band(y, qr[..., Q05], qr[..., Q95], eps))
            dband_max, dband_gt1 = max(dband_max, float(db.max())), dband_gt1 + int((db > 1).sum())
        for v, c in enumerate(targets):
            s = ch[c]
            s["moved"] += n
            s["dq"], s["dq_band"] = max(s["dq"], float(dq[v].max())), max(s["dq_band"], float(dqb[v].max()))
            s["dq_lv"] = max(s["dq_lv"], float(dq[v][..., BAND_LV].max()))
            s["gt01"] += int((dq[v] > 0.1).sum())
            if db is not None:
                s["dband"] = max(s["dband"], float(db[v].max()))
    nv = n_fc * len(QCOLS)
    rk, h8 = str(run_key(cfg)), run_dir(cfg).name.split("@")[-1]
    row = {"run_key": rk, "hash8": h8, "split": split, "device": cfg["model"]["device"], "calls": n_ctx,
           "calls_const": n_hit, "forecasts": n_fc, "forecasts_rerun": n_moved, "values": nv,
           "max_dq": top["dq"][0], "max_dq_channel": top["dq"][1], "max_dq_file": top["dq"][2],
           "max_dq_origin": top["dq"][3],
           **{f"share_dq_gt_{th:g}": (gt[th] / nv if nv else 0.0) for th in gt},
           "max_dq_q05_q50_q95": top["dq_lv"][0], "max_dq_q05_q50_q95_channel": top["dq_lv"][1],
           "max_dq_band": top["dq_band"][0], "max_dq_band_channel": top["dq_band"][1],
           "max_dband": dband_max if have_y else None,
           "share_dband_gt_1": (dband_gt1 / n_fc if n_fc else 0.0) if have_y else None}
    chans = [{"run_key": rk, "hash8": h8, "split": split, "channel": c, "forecasts_rerun": s["moved"],
              "max_dq": s["dq"], "max_dq_q05_q50_q95": s["dq_lv"], "share_dq_gt_0.1": s["gt01"] / (s["moved"] * len(QCOLS)),
              "max_dq_band": s["dq_band"], "max_dband": s["dband"] if have_y else None}
             for c, s in ch.items() if s["moved"]]
    return row, chans


def _upsert(path: Path, rows: list[dict], keys: list[tuple]) -> None:
    """Replace the rows of `keys` (run_key, hash8, split) in the CSV at `path` by `rows`."""
    parts = []
    if path.exists():
        old = pl.read_csv(path, infer_schema_length=0)
        drop = pl.any_horizontal([(pl.col("run_key") == r) & (pl.col("hash8") == h) & (pl.col("split") == sp)
                                  for r, h, sp in keys])
        parts.append(old.filter(~drop))
    if rows:
        parts.append(pl.DataFrame(rows, infer_schema_length=None).cast(pl.String))
    if parts:
        path.parent.mkdir(parents=True, exist_ok=True)
        pl.concat(parts, how="diagonal_relaxed").write_csv(path)


def done(cfg: dict, splits: list[str]) -> bool:
    """True when d128_effect.csv already has a row for this run key, forecast hash and each split."""
    path = Path(cfg["paths"]["results"]) / SUMMARY
    if not path.exists():
        return False
    df = pl.read_csv(path, infer_schema_length=0, columns=["run_key", "hash8", "split"])
    rk, h8 = str(run_key(cfg)), run_dir(cfg).name.split("@")[-1]
    have = set(df.filter((pl.col("run_key") == rk) & (pl.col("hash8") == h8))["split"].to_list())
    return set(splits) <= have


def run_d128(cfg: dict, split: str = "all", skip_done: bool = False) -> None:
    """Measure the D128 effect of one Chronos-2 run (rolling with in-file warm-up, cf-onset or frozen) per split."""
    if cfg["model"]["name"] != "chronos2":
        raise ValueError(f"the D128 guard is a Chronos-2 adapter detail; model.name is {cfg['model']['name']!r}")
    splits = forecast.splits_for(cfg, split)
    if skip_done and done(cfg, splits):
        print(f"d128 {run_key(cfg)}: up to date, skipped")
        return
    by_split = {sp: data.load_split(cfg, sp) for sp in splits}
    work = n_calls = 0
    mv = forecast.forecast_params(cfg)["multivariate"]
    for segs in by_split.values():
        for _, _, _, g, tgt, cov, _, _ in run_calls(cfg, segs):
            part = changed_part(g, tgt, cov, None, mv)
            if part is not None:
                n_calls += 2
                work += 2 * tgt.shape[1] * (len(part[1]) + (0 if part[2] is None else len(part[2])))
    per_step, per_call = LATENCY.get(cfg["model"]["device"], LATENCY["cpu"])
    print(f"d128 {run_key(cfg)} ({', '.join(splits)}): {n_calls // 2} calls hold a constant row; adapter and raw "
          f"model on each, estimate about {(work * per_step + n_calls * per_call) / 60:.1f} min", flush=True)
    pipe = forecast.load_forecaster(cfg["model"], cfg["paths"]["hf_cache"])   # the Timestral guard applies
    eps = cfg["score"]["eps"]
    rows, chans, keys = [], [], []
    for sp, segs in by_split.items():
        row, ch = measure(pipe, cfg, sp, segs, eps)
        rows.append(row)
        chans += ch
        keys.append((row["run_key"], row["hash8"], sp))
        print(f"  {sp}: {row['calls_const']} of {row['calls']} calls with a constant row; max |adapter - raw| "
              f"{row['max_dq']:.3g} z ({row['max_dq_channel']}), share of values > 0.01 / 0.1 / 1 z "
              f"{row['share_dq_gt_0.01']:.4f} / {row['share_dq_gt_0.1']:.4f} / {row['share_dq_gt_1']:.5f}; "
              f"q05/q50/q95 only {row['max_dq_q05_q50_q95']:.3g} z; max dq / band {row['max_dq_band']:.3g} "
              f"({row['max_dq_band_channel']}); max band-score change {row['max_dband']}", flush=True)
    out = Path(cfg["paths"]["results"])
    _upsert(out / SUMMARY, rows, keys)
    _upsert(out / CHANNELS, chans, keys)
