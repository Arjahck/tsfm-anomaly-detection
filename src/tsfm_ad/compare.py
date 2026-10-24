"""Methods compared at matched false-alarm rates, and paired bootstrap intervals (PLAN.md D135). Reads cached scores
and thresholds only, never the model. Writes results/<phase>/{fa_matched, bootstrap_ci, bootstrap_paired,
forecast_accuracy}.csv. No pick, threshold or selection reads these files.

Forecast accuracy (D136): per method and channel set, the mean mae (|q50 - y|) and crps per (channel, step) in fit-z,
and the share of (channel, step) with y inside [q05, q95] (nominal 0.90), on calib and on the normal and attack steps
of test. It compares forecasts, not detectors (chronos-2-small against the base model, Q19).

Matched false-alarm rate: for a target of F false-alarm steps per normal test hour, a method's threshold is the
score that leaves at most floor(F x normal hours) normal test steps above it. It is set from the test labels, like
reading one point of the ROC curve: an evaluation that compares methods at equal false alarms, not a detector. The
headline threshold stays the calib 99.5th percentile (D20).

Bootstrap: each test file is cut into blocks of `block_s`; a cut never falls inside an attack or the TaPR delta zone
after it. One resample draws as many blocks as there are, with replacement. Every method of a channel set gets the
same resamples (paired). Intervals are percentile intervals. TaPR of a resample joins its blocks like files (D31).
"""
from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, roc_auc_score

from tsfm_ad import baselines, data, evaluate, score, tapr_wrap
from tsfm_ad.config import load_config, resolve_selected, steps

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
NOTE = "threshold set from test labels; evaluation only, not a detector (D135)"


# ---- matched false-alarm thresholds ----

def fa_threshold(s, normal, fa_per_hour: float, res_s: int) -> float:
    """The threshold leaving at most floor(fa_per_hour x normal hours) normal steps with s > threshold. With ties at
    the cut fewer steps alarm; the achieved rate is reported next to the target."""
    sn = np.sort(np.asarray(s, np.float64)[np.asarray(normal, bool)])[::-1]
    k = int(math.floor(fa_per_hour * len(sn) * res_s / 3600 + 1e-9))
    return float(sn[k]) if k < len(sn) else -math.inf


def _tapr_f1(y_parts, a_parts, tc: dict, delta: int) -> dict:
    r = tapr_wrap.tapr(*tapr_wrap.join_files(list(zip(y_parts, a_parts)), delta + 1), delta=delta, alpha=tc["alpha"],
                       theta_r=tc.get("theta_r", tc.get("theta")), theta_p=tc.get("theta_p", tc.get("theta")))
    return {"TaP": r["TaP"], "TaR": r["TaR"], "tapr_f1": r["F1"]}


def _attack_rate(y, alarm) -> tuple[int, int]:
    runs = tapr_wrap.runs(y)
    return sum(bool(alarm[s:e + 1].any()) for s, e in runs), len(runs)


# ---- blocks and resamples ----

def blocks(label, bounds, block: int, delta: int) -> list[tuple[int, int]]:
    """(start, stop) positions of the blocks: each file [bounds[i], bounds[i+1]) cut every `block` steps, a cut moved
    forward past any attack and the `delta` steps after it. Blocks cover every step once, in order."""
    y = np.asarray(label).astype(bool)
    out = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        no_cut = np.zeros(b - a + 1, bool)              # no_cut[i]: no cut just before file step i
        for s, e in tapr_wrap.runs(y[a:b]):
            no_cut[s + 1:min(e + delta + 1, b - a + 1)] = True
        start, cut = a, a + block
        while cut < b:
            while cut < b and no_cut[cut - a]:
                cut += 1
            if cut < b:
                out.append((start, cut))
                start, cut = cut, cut + block
        out.append((start, b))
    return out


def resamples(n_blocks: int, B: int, seed: int) -> np.ndarray:
    """B x n_blocks block indices drawn with replacement; the same matrix serves every method (paired)."""
    return np.random.default_rng(seed).integers(0, n_blocks, size=(B, n_blocks))


# ---- metrics of one method on one (re)sample ----

def sample_metrics(s, y, parts, thr_calib: float, targets, res_s: int, tc: dict, delta: int) -> dict:
    """pr_auc, roc_auc and TaPR F1 at the calib threshold; recall, TaPR F1 and attack detection rate at each matched
    false-alarm target. `parts` = (start, stop) positions joined like files for TaPR."""
    out = {"pr_auc": float(average_precision_score(y, s)), "roc_auc": float(roc_auc_score(y, s))}
    ys = [y[a:b] for a, b in parts]
    out["tapr_f1_calib"] = _tapr_f1(ys, [s[a:b] > thr_calib for a, b in parts], tc, delta)["tapr_f1"]
    for F in targets:
        alarm = s > fa_threshold(s, ~y, F, res_s)
        out[f"recall_fa{F:g}"] = float(alarm[y].mean())
        out[f"tapr_f1_fa{F:g}"] = _tapr_f1(ys, [alarm[a:b] for a, b in parts], tc, delta)["tapr_f1"]
        det, n = _attack_rate(y, alarm)
        out[f"attack_rate_fa{F:g}"] = det / n if n else math.nan
    return out


def _boot_worker(args) -> np.ndarray:
    s, y, blks, idx, thr, targets, res_s, tc, delta = args
    rows = []
    for draw in idx:
        sel = [blks[j] for j in draw]
        ss = np.concatenate([s[a:b] for a, b in sel])
        yy = np.concatenate([y[a:b] for a, b in sel])
        lens = np.cumsum([0] + [b - a for a, b in sel])
        rows.append(list(sample_metrics(ss, yy, list(zip(lens[:-1], lens[1:])), thr, targets, res_s, tc,
                                        delta).values()))
    return np.asarray(rows, np.float64)


# ---- methods ----

def method_cfg(entry: str) -> dict:
    """A run config from a config file name or a baseline name."""
    if entry in baselines.BASELINES:
        return baselines.baseline_cfg(load_config(CONFIGS / "exp5_baselines.yaml"), entry)
    return resolve_selected(load_config(CONFIGS / entry))


def _load(cfg: dict, channel_set: str):
    d = score.source_dir(cfg)
    sd = d / "scores" / channel_set
    return (score.key_columns(cfg, d), pl.read_parquet(sd / "agg_test.parquet").sort("file", "t"),
            pl.read_parquet(sd / "thresholds.parquet"), d)


def accuracy_rows(d: Path, keys: dict, channels: list[str], channel_set: str, labels: pl.DataFrame) -> list[dict]:
    """Forecast accuracy of one run on one channel set from its per-channel scores (none for dual, which has none)."""
    full = sorted(d.glob("scores/*/scores_calib.parquet"))
    if len(full) != 1:
        return []
    rows = []
    for split in ("calib", "test"):
        s = pl.read_parquet(full[0].parent / f"scores_{split}.parquet").filter(pl.col("channel").is_in(channels))
        if not {"mae", "crps", "band"} <= set(s.columns):
            return []
        if s["channel"].n_unique() != len(channels):
            raise ValueError(f"{keys['run_key']}: {channel_set} has channels without scores")
        parts = {"calib": s} if split == "calib" else {
            f"test_{n}": s.join(labels, on=["file", "t"], how="inner").filter(pl.col("label") == v)
            for n, v in (("normal", 0), ("attack", 1))}
        for name, g in parts.items():
            rows.append({**keys, "channel_set": channel_set, "split": name, "n": g.height,
                         "mae_mean": g["mae"].mean(), "crps_mean": g["crps"].mean(),
                         "band_coverage": float((g["band"] == 0).mean()), "band_score_mean": g["band"].mean()})
    return rows


def _score_col(test: pl.DataFrame, kd: str, agg: str) -> str | None:
    """The column of score kd; the dual run has only its dual score, which stands in for band (its headline)."""
    if f"{kd}_{agg}" in test.columns:
        return f"{kd}_{agg}"
    return f"dual_{agg}" if kd == "band" and f"dual_{agg}" in test.columns else None


def run_compare(cfg: dict) -> None:
    c, res = cfg["compare"], cfg["dataset"]["resolution_s"]
    out = Path(cfg["paths"]["results"])
    tc = next(t for t in cfg["metrics"]["tapr"] if t["name"] == "headline")
    delta = steps(cfg, tc["delta_s"])
    N = steps(cfg, cfg["metrics"]["N_onset_s"])
    bs = c["bootstrap"]
    block, B, lo_q = steps(cfg, bs["block_s"]), bs["B"], (1 - bs["ci"]) / 2
    targets = [float(f) for f in c["fa_per_hour"]]
    metrics_csv = pl.read_csv(out / "metrics.csv")
    fa_rows, ci_rows, pair_rows, acc_rows = [], [], [], []
    sets_ch = data.channel_sets(cfg)
    for i_set, (name, spec) in enumerate(c["sets"].items()):
        entries = [spec["reference"], *spec["others"]]
        loaded = {e: _load(method_cfg(e), name) for e in entries}
        ref_test = loaded[spec["reference"]][1]
        for e, (_, t, _, _) in loaded.items():
            if not t.select("file", "t", "label").equals(ref_test.select("file", "t", "label")):
                raise ValueError(f"{e} on {name}: scored test steps differ from {spec['reference']}")
        y = ref_test["label"].to_numpy().astype(bool)
        bounds = np.cumsum([0] + ref_test.group_by("file", maintain_order=True).len()["len"].to_list())
        files = list(zip(bounds[:-1], bounds[1:]))
        attacks = evaluate._attacks_in(ref_test, data.load_attacks(cfg), N)
        origin, h = ref_test["origin"].to_numpy(), ref_test["h"].to_numpy()
        labels = ref_test.select("file", "t", "label")
        for keys, _, _, d in loaded.values():
            acc_rows += accuracy_rows(d, keys, sets_ch[name], name, labels)
        blks = blocks(y, bounds, block, delta)
        idx = resamples(len(blks), B, bs["seed"] + i_set)
        for kd in c["scores"]:
            jobs, meta = [], []
            for e, (keys, t, thr, _) in loaded.items():
                col = _score_col(t, kd, c["agg"])
                if col is None:
                    continue
                s = t[col].to_numpy().astype(np.float64)
                skd = col.rsplit("_", 1)[0]
                thr_c = thr.filter((pl.col("score") == skd) & (pl.col("agg") == c["agg"])
                                   & (pl.col("calib_source") == "calib"))["threshold"].item()
                pr = metrics_csv.filter((pl.col("run_key") == keys["run_key"]) & (pl.col("hash8") == keys["hash8"])
                                        & (pl.col("channel_set") == name) & (pl.col("score") == skd)
                                        & (pl.col("agg") == c["agg"]) & (pl.col("calib_source") == "calib"))
                full = sample_metrics(s, y, files, thr_c, targets, res, tc, delta)
                if pr.height != 1 or abs(pr["pr_auc"].item() - full["pr_auc"]) > 1e-9:
                    raise ValueError(f"{keys['run_key']} {name} {skd}: pr_auc does not match metrics.csv")
                base = {**keys, "channel_set": name, "score": skd, "agg": c["agg"]}
                for F in targets:
                    th = fa_threshold(s, ~y, F, res)
                    alarm = s > th
                    pm = evaluate.point_metrics(s, y, th, res)
                    det, n = _attack_rate(y, alarm)
                    seg = evaluate.segment_table(alarm, s, attacks, origin, h, res)
                    fa_rows.append({**base, "target_fa_per_hour": F, "threshold": th,
                                    **{k: pm[k] for k in ("fa_per_hour", "alarm_steps", "precision", "recall", "f1")},
                                    **_tapr_f1([y[a:b] for a, b in files], [alarm[a:b] for a, b in files], tc, delta),
                                    "attacks_detected": det, "n_attacks": n,
                                    "onset_cov_mean": seg["onset_cov"].mean(),
                                    "interior_cov_mean": seg["interior_cov"].mean(),
                                    "offset_cov_mean": seg["offset_cov"].mean(), "note": NOTE})
                jobs.append((s, y, blks, idx, thr_c, targets, res, tc, delta))
                meta.append((e, base, full))
            with ProcessPoolExecutor(max_workers=c.get("workers", 8)) as ex:
                boots = list(ex.map(_boot_worker, jobs))
            names = list(meta[0][2])
            for (e, base, full), bt in zip(meta, boots):
                for j, m in enumerate(names):
                    ci_rows.append({**base, "metric": m, "estimate": full[m],
                                    "lo": float(np.nanquantile(bt[:, j], lo_q)),
                                    "hi": float(np.nanquantile(bt[:, j], 1 - lo_q)), "B": B, "block_s": bs["block_s"]})
            ref = next(i for i, (e, _, _) in enumerate(meta) if e == spec["reference"])
            for i, (e, base, full) in enumerate(meta):
                if i == ref:
                    continue
                rb, rf = meta[ref][1], meta[ref][2]
                for j, m in enumerate(names):
                    d = boots[ref][:, j] - boots[i][:, j]
                    pair_rows.append({"channel_set": name, "score": kd, "agg": c["agg"], "metric": m,
                                      "reference": rb["run_key"], "reference_hash8": rb["hash8"],
                                      "reference_score": rb["score"], "other": base["run_key"],
                                      "other_hash8": base["hash8"], "other_score": base["score"],
                                      "diff": rf[m] - full[m], "lo": float(np.nanquantile(d, lo_q)),
                                      "hi": float(np.nanquantile(d, 1 - lo_q)),
                                      "share_reference_higher": float(np.nanmean(d > 0)), "B": B,
                                      "block_s": bs["block_s"]})
        print(f"compare {name}: {len(entries)} methods, {len(blks)} blocks, B = {B}")
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(fa_rows).write_csv(out / "fa_matched.csv")
    pl.DataFrame(ci_rows).write_csv(out / "bootstrap_ci.csv")
    pl.DataFrame(pair_rows).write_csv(out / "bootstrap_paired.csv")
    pl.DataFrame(acc_rows).write_csv(out / "forecast_accuracy.csv")
    print(f"compare: fa_matched.csv, bootstrap_ci.csv, bootstrap_paired.csv, forecast_accuracy.csv in {out}")
