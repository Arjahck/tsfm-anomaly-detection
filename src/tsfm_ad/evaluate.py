"""Metrics from the scores (PLAN.md sections 9 and 12; D29-D32, D44-D50). Reads scores and the cache, never the model.

run_evaluate(cfg) upserts results/<phase>/{metrics, tapr, segments_per_attack, segments_summary, segments_by_h,
band_width_by_h, cf_onset}.csv. Every row carries the run-key columns and channel_set. All step indices below are
positions in the scored test steps of the run, sorted by (file, t); scored steps of a file are contiguous (t >= W).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, roc_auc_score

from tsfm_ad import cache, context, data, ff_results, score, tapr_wrap
from tsfm_ad.config import steps
from tsfm_ad.summary import (FF_GROUPS, METHOD, RUN_COLS, SEGMENTS, cf_onset_table, common_detected,  # noqa: F401
                             evaluate_cf, key_lits, latency_summary, run_rows, summarize, update_summary)

FF_COLS = ["ff_group", "ff_active_at_onset", "ff_n_channels_active_at_onset", "ff_fallback_age_at_onset_steps",
           "ff_first_trigger_after_onset_steps"]
SEG_COLS = [f"{s}_{x}" for s in SEGMENTS for x in ("n", "det", "cov", "chance")]
ATTACK_COLS = (["attack_id", "stratum", "duration_steps", *SEG_COLS, "latency_s", "latency_censored_s",
                "n_post_origin", "cov_post_origin", "n_pre_origin", "cov_pre_origin", *FF_COLS, "p_normal"])


# ---- point metrics ----

def point_metrics(score_, label, thr, res_s=10) -> dict:
    """AUCs on the continuous score; precision, recall, F1, alarm steps and false-alarm steps per normal hour at thr."""
    s, y = np.asarray(score_, np.float64), np.asarray(label).astype(bool)
    alarm = s > thr
    tp, fp, fn = int((alarm & y).sum()), int((alarm & ~y).sum()), int((~alarm & y).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    both = bool(y.any() and (~y).any())
    normal_h = (~y).sum() * res_s / 3600
    return {"roc_auc": float(roc_auc_score(y, s)) if both else math.nan,
            "pr_auc": float(average_precision_score(y, s)) if both else math.nan,
            "precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "alarm_steps": int(alarm.sum()), "fa_per_hour": fp / normal_h if normal_h else math.nan}


def pa_f1(alarm, label) -> float:
    """Point-adjusted F1: an attack with any alarm counts as fully detected. Inflated; never a headline."""
    a, y = np.asarray(alarm).astype(bool).copy(), np.asarray(label).astype(bool)
    for s, e in tapr_wrap.runs(y):
        if a[s:e + 1].any():
            a[s:e + 1] = True
    tp, fp, fn = (a & y).sum(), (a & ~y).sum(), (~a & y).sum()
    return float(2 * tp / (2 * tp + fp + fn)) if tp else 0.0


# ---- attack segments (D29, D45) ----

@dataclass(frozen=True)
class Attack:
    start: int            # first attack step
    end: int              # last attack step, inclusive
    N: int
    onset: range          # first N attack steps
    interior: range       # the rest of the attack (empty if L <= N)
    interior_eq: range    # attack steps N+1..2N (empty if L < 2N)
    offset: range         # the N steps after the end, cut at the next attack and the array end
    attack_id: str = ""
    stratum: str = ""

    def shifted(self, base: int) -> "Attack":
        sh = {k: range(r.start + base, r.stop + base) for k, r in
              (("onset", self.onset), ("interior", self.interior), ("interior_eq", self.interior_eq),
               ("offset", self.offset))}
        return replace(self, start=self.start + base, end=self.end + base, **sh)


def segments(label, N: int) -> list[Attack]:
    """Onset, interior, interior_eq and offset of every run of 1 in one file's label array."""
    y = np.asarray(label).astype(np.int8)
    d = np.diff(np.concatenate([[0], y, [0]]))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    out = []
    for i, (s, e) in enumerate(zip(starts.tolist(), ends.tolist())):
        nxt = starts[i + 1] if i + 1 < len(starts) else len(y)
        eq = range(s + N, s + 2 * N) if e - s + 1 >= 2 * N else range(0)
        out.append(Attack(s, e, N, range(s, min(s + N, e + 1)), range(min(s + N, e + 1), e + 1), eq,
                          range(e + 1, min(e + N + 1, nxt))))
    return out


def chance_level(p: float, n: int) -> float:
    """Chance of at least one alarm in n steps with independent alarms at rate p: 1 - (1 - p)^n (D45)."""
    return 1.0 - (1.0 - p) ** n


def _normal_rate(alarm, attacks) -> float:
    normal = np.ones(len(alarm), bool)
    for a in attacks:
        normal[a.start:a.end + 1] = False
    return float(alarm[normal].mean()) if normal.any() else math.nan


def segment_table(alarm, score_, attacks, origin, h, steps_res, ff_state=None, p_normal=None) -> pl.DataFrame:
    """One row per attack: segment detection, coverage and chance level, latency (a miss is censored at duration +
    N), and attack-step coverage split by forecast origin (post-onset: origin > onset step, so the context holds
    attack data). p_normal defaults to the alarm rate on the steps outside every attack."""
    alarm, origin, h = np.asarray(alarm).astype(bool), np.asarray(origin), np.asarray(h)
    p = _normal_rate(alarm, attacks) if p_normal is None else p_normal
    rows = []
    for a in attacks:
        L = a.end - a.start + 1
        r = {"attack_id": a.attack_id, "stratum": a.stratum, "duration_steps": L}
        for name in SEGMENTS:
            seg = alarm[getattr(a, name).start:getattr(a, name).stop]
            n = len(seg)
            r.update({f"{name}_n": n, f"{name}_det": bool(seg.any()) if n else None,
                      f"{name}_cov": float(seg.mean()) if n else None,
                      f"{name}_chance": chance_level(p, n) if n else None})
        hit = np.flatnonzero(alarm[a.start:a.end + 1])
        r["latency_s"] = int(hit[0]) * steps_res if len(hit) else None
        r["latency_censored_s"] = r["latency_s"] if len(hit) else (L + a.N) * steps_res
        post = origin[a.start:a.end + 1] > origin[a.start] + h[a.start] - 1
        al = alarm[a.start:a.end + 1]
        r.update({"n_post_origin": int(post.sum()), "cov_post_origin": float(al[post].mean()) if post.any() else None,
                  "n_pre_origin": int((~post).sum()),
                  "cov_pre_origin": float(al[~post].mean()) if (~post).any() else None})
        rows.append(r)
    if not rows:
        return pl.DataFrame(schema={c: pl.Null for c in ATTACK_COLS})
    tab = pl.DataFrame(rows, infer_schema_length=None)
    if ff_state is not None and tab.height:
        tab = tab.join(ff_state, on="attack_id", how="left")
    else:
        tab = tab.with_columns(*[pl.lit(None).alias(c) for c in FF_COLS])
    return tab.with_columns(p_normal=pl.lit(p, pl.Float64)).select(ATTACK_COLS)


def _bucket(v, buckets) -> np.ndarray:
    out = np.full(len(v), None, object)
    for lo, hi in buckets:
        m = (v >= lo) & (v <= (np.inf if hi is None else hi))
        out[m] = f"{lo}-{hi}" if hi is not None else f"{lo}+"
    return out


def segments_by_h(alarm, score_, attacks, origin, h, steps_res, h_buckets, tso_buckets) -> pl.DataFrame:
    """Coverage and mean score by segment x origin side x h bucket x time-since-onset bucket, pooled over attacks."""
    alarm, score_, origin, h = (np.asarray(x) for x in (alarm, score_, origin, h))
    parts = []
    for a in attacks:
        for name in SEGMENTS:
            idx = np.arange(getattr(a, name).start, getattr(a, name).stop)
            if len(idx):
                parts.append(pl.DataFrame({
                    "attack_id": [a.attack_id] * len(idx), "segment": [name] * len(idx),
                    "origin_side": np.where(origin[idx] > origin[a.start] + h[a.start] - 1, "post", "pre"),
                    "h_bucket": _bucket(h[idx], h_buckets), "tso_bucket": _bucket((idx - a.start) * steps_res,
                                                                                    tso_buckets),
                    "alarm": alarm[idx].astype(np.float64), "score": score_[idx].astype(np.float64)},
                    schema_overrides={"h_bucket": pl.String, "tso_bucket": pl.String}))
    cols = ["segment", "origin_side", "h_bucket", "tso_bucket"]
    if not parts:
        return pl.DataFrame(schema={**{c: pl.String for c in cols}, "n_steps": pl.UInt32, "n_attacks": pl.UInt32,
                                    "coverage": pl.Float64, "mean_score": pl.Float64})
    return (pl.concat(parts).drop_nulls(["h_bucket", "tso_bucket"])
            .group_by(cols).agg(n_steps=pl.len(), n_attacks=pl.col("attack_id").n_unique(),
                                coverage=pl.col("alarm").mean(), mean_score=pl.col("score").mean())
            .sort(cols))


# ---- band width (D46) ----

def band_width_by_h(q: pl.DataFrame, sets: dict) -> pl.DataFrame:
    """Median and mean of q95 - q05 (z units) by h, per channel set; q has channel, h, q05, q95."""
    parts = [q.filter(pl.col("channel").is_in(members)).group_by("h")
             .agg(band_median=(pl.col("q95") - pl.col("q05")).median(), band_mean=(pl.col("q95") - pl.col("q05")).mean())
             .with_columns(channel_set=pl.lit(name)) for name, members in sets.items()]
    return pl.concat(parts).sort("channel_set", "h").select("channel_set", "h", "band_median", "band_mean")


# ---- run_evaluate ----

def _attacks_in(test: pl.DataFrame, attack_tab: pl.DataFrame, N: int) -> list[Attack]:
    """Attacks as positions in the scored test steps (sorted by file, t), with id and stratum from attacks.parquet."""
    out, base = [], 0
    for (f,), g in test.group_by(["file"], maintain_order=True):
        t = g["t"].to_numpy()
        if (np.diff(t) != 1).any():
            raise ValueError(f"scored steps of {f} are not contiguous")
        meta = {(s, e): (aid, st) for aid, s, e, st in attack_tab.filter(pl.col("segment") == f)
                .select("attack_id", "start_idx", "end_idx", "stratum").iter_rows()}
        found = [a for a in segments(g["label"].to_numpy(), N)]
        spans = [(int(t[a.start]), int(t[a.end])) for a in found]
        if sorted(spans) != sorted(meta):
            raise ValueError(f"cached labels of {f} give attacks {spans}, attacks.parquet has {sorted(meta)}")
        out += [replace(a.shifted(base), attack_id=meta[sp][0], stratum=meta[sp][1]) for a, sp in zip(found, spans)]
        base += g.height
    lost = sorted(set(attack_tab["attack_id"]) - {a.attack_id for a in out})
    if lost:
        raise ValueError(f"attacks {lost} of attacks.parquet are not in the scored test steps: run forecast and score")
    return out


def _evaluate_run(cfg, d, man, keys, out) -> None:
    kind, res = cfg["variant"]["kind"], cfg["dataset"]["resolution_s"]
    hl_calib, hl_score = man["calib_sources"][0], ("dual" if kind == "dual" else "band")
    hl_agg = man["columns"][0][1]
    m = cfg["metrics"]
    Ns = [steps(cfg, m["N_onset_s"])] + [steps(cfg, n) for n in m.get("N_sensitivity_s") or []]
    attack_tab = data.load_attacks(cfg)
    ff = {}
    if kind == "ff":  # D44: from the episodes the FF forecast wrote, over every channel of the setup
        names = [c for g in data.setup_groups(cfg, keys["setup"]) for c in g.targets]
        ff_results.write_ff_results(cfg, d, keys, context.ff_tau(cfg), names)
        episodes = ff_results.read_episodes(d).filter(pl.col("split") == "test")
        ff = {N: ff_results.ff_attack_state(episodes, attack_tab, N) for N in Ns}
    metrics, taprs, per_attack, by_h, groups = [], [], [], [], set()
    for name in man["sets"]:
        sd = d / "scores" / name
        test = pl.read_parquet(sd / "agg_test.parquet").sort("file", "t")
        thr = pl.read_parquet(sd / "thresholds.parquet")
        label, origin, h = (test[c].to_numpy() for c in ("label", "origin", "h"))
        bounds = np.cumsum([0] + test.group_by("file", maintain_order=True).len()["len"].to_list())
        attacks = {N: _attacks_in(test, attack_tab, N) for N in Ns}
        for kd, ag in man["columns"]:
            s = test[f"{kd}_{ag}"].to_numpy()
            base = {"channel_set": name, "score": kd, "agg": ag}
            for c_src, t_val in thr.filter((pl.col("score") == kd) & (pl.col("agg") == ag)) \
                    .select("calib_source", "threshold").iter_rows():
                metrics.append({**base, "calib_source": c_src, **point_metrics(s, label, t_val, res),
                                "pa_f1_inflated": pa_f1(s > t_val, label)})
            alarm = s > thr.filter((pl.col("score") == kd) & (pl.col("agg") == ag)
                                   & (pl.col("calib_source") == hl_calib))["threshold"].item()
            pairs = [(label[a:b], alarm[a:b]) for a, b in zip(bounds[:-1], bounds[1:])]   # one pair per file
            for tc in m["tapr"]:
                delta = steps(cfg, tc["delta_s"])
                th_r, th_p = tc.get("theta_r", tc.get("theta")), tc.get("theta_p", tc.get("theta"))
                r = tapr_wrap.tapr(*tapr_wrap.join_files(pairs, delta + 1), delta=delta, alpha=tc["alpha"],
                                   theta_r=th_r, theta_p=th_p)
                taprs.append({**base, "config": tc["name"], "alpha": tc["alpha"], "theta_r": th_r, "theta_p": th_p,
                              "delta_steps": delta, "delta_s": tc["delta_s"],
                              **{k: r[k] for k in ("TaP", "TaP_d", "TaP_p", "TaR", "TaR_d", "TaR_p", "F1",
                                                   "n_pred_ranges")}})
            for N in Ns if (kd, ag) == (hl_score, hl_agg) else Ns[:1]:
                tab = segment_table(alarm, s, attacks[N], origin, h, res, ff_state=ff.get(N))
                per_attack.append(tab.with_columns(*key_lits(base), N=pl.lit(N)))
                groups.add((keys["dataset"], name, "headline" if kd in ("band", "dual") else kd, ag, str(N)))
                if N == Ns[0]:
                    by_h.append(segments_by_h(alarm, s, attacks[N], origin, h, res, m["h_buckets"],
                                              m["tso_buckets_s"]).with_columns(*key_lits(base), N=pl.lit(N)))
    front = ["channel_set", "score", "agg"]
    score.upsert_csv(out / "metrics.csv", run_rows(pl.DataFrame(metrics), keys, front + ["calib_source"]),
                     ["run_key", *front, "calib_source"])
    score.upsert_csv(out / "tapr.csv", run_rows(pl.DataFrame(taprs), keys, front + ["config"]),
                     ["run_key", *front, "config"])
    score.upsert_csv(out / "segments_per_attack.csv",
                     run_rows(pl.concat(per_attack, how="diagonal_relaxed"), keys, front + ["N"]),
                     ["run_key", *front, "N", "attack_id"])
    score.upsert_csv(out / "segments_by_h.csv", run_rows(pl.concat(by_h), keys, front + ["N"]),
                     ["run_key", *front, "N", "segment", "origin_side", "h_bucket", "tso_bucket"])
    update_summary(out, groups)


def run_evaluate(cfg: dict) -> None:
    kind = cfg["variant"]["kind"]
    d = score.source_dir(cfg)
    man = score.read_manifest(cfg, d)
    keys = score.key_columns(cfg, d)
    out = Path(cfg["paths"]["results"])
    (evaluate_cf if kind == "cf-onset" else _evaluate_run)(cfg, d, man, keys, out)
    if kind == "dual":
        print(f"evaluated {keys['run_key']}@{keys['hash8']}")
        return
    if kind == "frozen":
        q = {"ref": cache.read_ref(cfg)}
    else:
        q = {s: pl.scan_parquet(cache.split_paths(cfg, d, s)).select("channel", "h", "q05", "q95").collect()
             for s in man["splits"]}
    bw = [band_width_by_h(v, man["sets"]).with_columns(split=pl.lit(s)) for s, v in q.items()]
    score.upsert_csv(out / "band_width_by_h.csv", run_rows(pl.concat(bw), keys, ["channel_set", "split", "h"]),
                     ["run_key", "channel_set", "split", "h"])
    print(f"evaluated {keys['run_key']}@{keys['hash8']}: results in {out}")
