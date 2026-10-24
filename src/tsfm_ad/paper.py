"""The paper (paper/paper.typ, D153): its tables and figures from results/phase1 and results/phase2, plus the origin
split of the LANL injections from the Phase 2 cache (forecasts and labels only, no model call). Writes
results/paper/*.csv and results/paper/figures/*.svg, then compiles paper/paper.pdf when the `paper` extra (typst) is
installed. Not a hashed source.

Contamination share (kappa): the share of anomaly steps scored by a forecast whose origin lies after the anomaly's
first step, so that its context already holds anomalous data (the Phase 1 `n_post_origin` rule, evaluate.py).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

P1, P2, OUT = Path("results/phase1"), Path("results/phase2"), Path("results/paper")
MODEL = "chronos2-29ec376-mps"
# key, label, dataset, variant, segment N (steps), stride S (= H); all `uni` on uni51, band score, top-3
HAI = [("hai-10s-h30", "HAI 10 s, H = 30, history 8,192", "hai2103-10s", "rolling", 6, 30),
       ("hai-10s-c128", "HAI 10 s, H = 30, history 128", "hai2103-10s", "rolling-c128", 6, 30),
       ("hai-10s-h6", "HAI 10 s, H = 6, history 8,192", "hai2103-10s", "rolling-h6", 6, 6),
       ("hai-1s-c128", "HAI 1 s, H = 30, history 128", "hai2103-1s", "rolling-c128", 60, 30)]
LANL = ("lanl-mv", "LANL 1 min, H = 30, history 8,192", 30, 30)
SPLIT_RUNS = ("lastvalue", "robustz")          # baselines that forecast from the recent context
P2_RUNS = ["mv", "mv-cov", "mv-frozen", "mv-dual", "mv-ff", "lastvalue", "seasonal-naive", "robustz"]
P2_SCORE = {"mv-dual": "dual"}                 # every other Phase 2 run on the band score
C_CLEAN, C_CONT, C_ONSET, C_INT = "#2e8b57", "#c0392b", "#8a8a8a", "#2f6db5"


def kappa_hat(L, S: int) -> np.ndarray:
    """Expected contamination share of anomalies of length L (steps) when the forecast grid's phase is uniform: the
    first origin after the onset falls d = 1..S steps in, and the L - d steps from there on are contaminated."""
    L = np.atleast_1d(np.asarray(L, float))
    d = np.arange(1, S + 1)
    return np.clip(L[:, None] - d[None, :], 0, None).mean(axis=1) / L


def kappa_r(r) -> np.ndarray:
    """The continuous limit of kappa_hat in r = L / S: r / 2 for r <= 1, 1 - 1 / (2 r) above."""
    r = np.asarray(r, float)
    return np.where(r <= 1, r / 2, 1 - 1 / (2 * np.maximum(r, 1e-12)))


def origin_split(t, origin, alarm, start: int, end: int, width=None) -> dict:
    """Steps, contaminated steps and alarms of one anomaly [start, end) by origin side (post: origin > start); with
    `width`, also its sums on each side."""
    t, origin, alarm = np.asarray(t), np.asarray(origin), np.asarray(alarm, bool)
    m = (t >= start) & (t < end)
    post = m & (origin > start)
    pre = m & ~post
    r = {"L": int(m.sum()), "n_post": int(post.sum()), "n_pre": int(pre.sum()),
         "a_post": int(alarm[post].sum()), "a_pre": int(alarm[pre].sum())}
    if width is not None:
        w = np.asarray(width)
        r.update(w_post=float(w[post].sum()), w_pre=float(w[pre].sum()))
    return r


def grid_phase(onset, first_origin: int, S: int) -> np.ndarray:
    """Steps from the last forecast origin at or before the onset to the onset (0 = the onset opens a forecast)."""
    return (np.asarray(onset) - first_origin) % S


# ---- tables ----

def _hai_rows(setup: str, model: str, variant: str, dataset: str, N: int, score: str = "band") -> pl.DataFrame:
    s = pl.read_csv(P1 / "segments_per_attack.csv", infer_schema_length=None)
    g = s.filter((pl.col("dataset") == dataset) & (pl.col("model") == model) & (pl.col("setup") == setup)
                 & (pl.col("variant") == variant) & (pl.col("channel_set") == "uni51") & (pl.col("score") == score)
                 & (pl.col("agg") == "topk") & (pl.col("N") == N))
    assert g.height == 50, (setup, variant, dataset, score, g.height)
    return g


def _hai_split(g: pl.DataFrame) -> pl.DataFrame:
    g = g.with_columns(pl.col("cov_post_origin", "cov_pre_origin").fill_null(0.0))
    assert (g["n_post_origin"] + g["n_pre_origin"] == g["duration_steps"]).all()
    return g.select(attack_id="attack_id", L="duration_steps", n_post="n_post_origin", n_pre="n_pre_origin",
                    a_post=(pl.col("n_post_origin") * pl.col("cov_post_origin")).round().cast(pl.Int64),
                    a_pre=(pl.col("n_pre_origin") * pl.col("cov_pre_origin")).round().cast(pl.Int64))


def _lanl_split(run: str) -> tuple[pl.DataFrame, float]:
    """Per injection, all seeds and the band and mae scores, from the Phase 2 cache and the run's calib thresholds;
    with the band width q95 - q05 (fit-z). Also the mean band width on the normal test minutes (label 0)."""
    from tsfm_ad import p2, p2_eval

    cfg = p2.load_cfg("configs/phase2.yaml")
    data, eps = p2.Data(cfg), cfg["score"]["eps"]
    thr = pl.read_csv(P2 / "thresholds.csv").filter(pl.col("run") == run)
    T = {(r["score"], r["series"]): r["threshold"] for r in thr.iter_rows(named=True)}
    man = pl.read_csv(P2 / "injections.csv")
    rows, wn, nn = [], 0.0, 0
    for seed in cfg["inject"]["seeds"]:
        f = p2.read(cfg, run, f"seed{seed}", data)
        sc = p2_eval.scored(f, eps).with_columns(origin=f["origin"], width=f["q95"] - f["q05"])
        normal = sc.filter(pl.col("label") == 0)["width"]
        wn, nn = wn + float(normal.sum()), nn + normal.len()
        by = {k[0]: g.sort("t") for k, g in sc.group_by("series")}
        for r in man.filter(pl.col("seed") == seed).iter_rows(named=True):
            g = by[r["series"]]
            for score in ("band", "mae"):
                rows.append({"inj_id": r["inj_id"], "seed": seed, "type": r["type"], "score": score,
                             "duration_min": r["duration_min"],
                             **origin_split(g["t"], g["origin"], g[score].to_numpy() > T[(score, r["series"])],
                                            r["start"], r["end"], g["width"])})
    return pl.DataFrame(rows), wn / nn


def _p_normal(setting: str, score: str) -> float:
    """Share of normal steps that alarm (segments_summary.csv for HAI, false_alarms.csv for LANL `mv`)."""
    if setting == LANL[0]:
        fa = pl.read_csv(P2 / "false_alarms.csv").filter((pl.col("run") == "mv") & (pl.col("score") == score))
        return fa["alarms"].sum() / fa["normal_minutes"].sum()
    _, _, ds, var, N, _ = next(h for h in HAI if h[0] == setting)
    s = pl.read_csv(P1 / "segments_summary.csv", infer_schema_length=None)
    return s.filter((pl.col("dataset") == ds) & (pl.col("model") == MODEL) & (pl.col("setup") == "uni")
                    & (pl.col("variant") == var) & (pl.col("channel_set") == "uni51") & (pl.col("score") == score)
                    & (pl.col("agg") == "topk") & (pl.col("N") == N) & (pl.col("stratum") == "all")
                    & (pl.col("ff_group") == "all"))["p_normal"][0]


def _pooled(g: pl.DataFrame, mae: pl.DataFrame | None = None) -> dict:
    """kappa and coverage by origin side, pooled over the anomaly steps; with `mae`, the same split on that score."""
    n_post, n_pre = g["n_post"].sum(), g["n_pre"].sum()
    r = {"anomalies": g.height, "steps": int(g["L"].sum()), "kappa": n_post / (n_post + n_pre),
         "c_pre": g["a_pre"].sum() / n_pre if n_pre else None, "c_post": g["a_post"].sum() / n_post if n_post
         else None, "coverage": (g["a_pre"].sum() + g["a_post"].sum()) / (n_post + n_pre)}
    if mae is not None:
        r.update(mae_c_pre=mae["a_pre"].sum() / n_pre, mae_c_post=mae["a_post"].sum() / n_post)
    return r


def kappa_tables() -> tuple[pl.DataFrame, pl.DataFrame]:
    """kappa_anomalies.csv (one row per anomaly and setting) and origin_split.csv (pooled per setting and method)."""
    per, split = [], []
    for key, label, ds, var, N, S in HAI:
        g = _hai_split(_hai_rows("uni", MODEL, var, ds, N))
        per.append(g.with_columns(setting=pl.lit(key), S=pl.lit(S), r=pl.col("L") / S,
                                  kappa_i=pl.col("n_post") / pl.col("L"),
                                  kappa_hat_i=pl.Series(kappa_hat(g["L"].to_numpy(), S))))
        split.append({"setting": key, "label": label, "method": "Chronos-2", "S": S,
                      "kappa_hat": float((kappa_hat(g["L"].to_numpy(), S) * g["L"].to_numpy()).sum() / g["L"].sum()),
                      "p_band": _p_normal(key, "band"), "p_mae": _p_normal(key, "mae"),
                      **_pooled(g, _hai_split(_hai_rows("uni", MODEL, var, ds, N, "mae")))})
        if var in ("rolling", "rolling-c128") and key != "hai-10s-c128":
            bvar = "rolling" if ds == "hai2103-10s" else "rolling-c8192"     # 1 s baselines: no history cap
            for b in SPLIT_RUNS:                     # baselines have no history cap
                split.append({"setting": key, "label": label.split(", history")[0], "method": b, "S": S,
                              "kappa_hat": None,
                              **_pooled(_hai_split(_hai_rows(b, "baseline", bvar, ds, N)))})
    key, label, N, S = LANL
    for run in ("mv", "mv-cov", *SPLIT_RUNS):
        both, w_normal = _lanl_split(run)
        g, mae = both.filter(pl.col("score") == "band"), both.filter(pl.col("score") == "mae")
        if run == "mv":
            width = {"setting": key, "w_normal": w_normal, "w_pre": g["w_pre"].sum() / g["n_pre"].sum(),
                     "w_post": g["w_post"].sum() / g["n_post"].sum()}
            per.append(g.select("L", "n_post", "n_pre", "a_post", "a_pre",
                                attack_id=pl.col("inj_id") + "/" + pl.col("seed").cast(pl.Utf8))
                       .with_columns(setting=pl.lit(key), S=pl.lit(S), r=pl.col("L") / S,
                                     kappa_i=pl.col("n_post") / pl.col("L"),
                                     kappa_hat_i=pl.Series(kappa_hat(g["L"].to_numpy(), S))))
        split.append({"setting": key, "label": label if run.startswith("mv") else label.split(", history")[0],
                      "method": {"mv": "Chronos-2", "mv-cov": "Chronos-2 + covariates"}.get(run, run), "S": S,
                      "kappa_hat": float((kappa_hat(g["L"].to_numpy(), S) * g["L"].to_numpy()).sum() / g["L"].sum()),
                      **({"p_band": _p_normal(key, "band"), "p_mae": _p_normal(key, "mae")} if run == "mv" else {}),
                      **_pooled(g, mae)})
    cols = ["setting", "attack_id", "S", "L", "r", "n_post", "n_pre", "a_post", "a_pre", "kappa_i", "kappa_hat_i"]
    return (pl.concat([p.select(cols) for p in per]), pl.DataFrame(split, infer_schema_length=None),
            pl.DataFrame([width]))


def phase_table() -> pl.DataFrame:
    """Where the HAI onsets fall in the forecast grid (attacks.csv start step, first origin = the warm-up end)."""
    from tsfm_ad.config import load_config

    W_s = load_config("configs/base.yaml")["forecast"]["W_s"]
    files = pl.read_csv(P1 / "splits.csv").filter((pl.col("split") == "test") & (pl.col("resolution_s") == 1))
    a = pl.read_csv(P1 / "attacks.csv").join(files.select(file="segment", file_start="start"), on="file")
    s1 = ((a["start"].str.to_datetime() - a["file_start"].str.to_datetime()).dt.total_seconds()).to_numpy()
    assert (s1 // 10 == a["history_steps"].to_numpy()).all()
    rows = []
    for key, S, onset, first in (("hai-10s-h30", 30, s1 // 10, W_s // 10), ("hai-10s-h6", 6, s1 // 10, W_s // 10),
                                 ("hai-1s-c128", 30, s1, W_s)):
        ph = grid_phase(onset, first, S)
        rows.append({"setting": key, "S": S, "anomalies": len(ph), "at_origin": int((ph == 0).sum()),
                     "expected_at_origin": len(ph) / S})
    return pl.DataFrame(rows)


def cf_table() -> pl.DataFrame:
    """The clean-context counterfactual (cf-onset, a diagnostic) on the contaminated interior steps, `uni` on uni51."""
    cf = pl.read_csv(P1 / "cf_onset.csv", infer_schema_length=None)
    cf = cf.filter((pl.col("setup") == "uni") & (pl.col("channel_set") == "uni51") & (pl.col("score") == "band")
                   & (pl.col("agg") == "topk") & (pl.col("segment") == "interior") & (pl.col("origin_side") == "post"))
    w = pl.col("n_steps")
    return (cf.group_by("dataset").agg(steps=w.sum(), attacks=pl.len(),
                                       c_rolling=(w * pl.col("cov_rolling")).sum() / w.sum(),
                                       c_cf=(w * pl.col("cov_cf")).sum() / w.sum(),
                                       cf_score_higher=(pl.col("score_cf_mean") > pl.col("score_rolling_mean")).sum())
            .with_columns(setting=pl.col("dataset").replace_strict({"hai2103-10s": "hai-10s-h30",
                                                                     "hai2103-1s": "hai-1s-c128"}))
            .sort("dataset"))


def segments_table() -> pl.DataFrame:
    """Onset / interior / offset coverage and detection per Chronos-2 setting (segments_summary.csv; LANL from
    detections.csv and false_alarms.csv, N = 30 min)."""
    s = pl.read_csv(P1 / "segments_summary.csv", infer_schema_length=None)
    m = pl.read_csv(P1 / "metrics.csv", infer_schema_length=None)
    rows = []
    for key, label, ds, var, N, S in HAI:
        f = ((pl.col("dataset") == ds) & (pl.col("model") == MODEL) & (pl.col("setup") == "uni")
             & (pl.col("variant") == var) & (pl.col("channel_set") == "uni51") & (pl.col("score") == "band")
             & (pl.col("agg") == "topk"))
        r = s.filter(f & (pl.col("N") == N) & (pl.col("stratum") == "all") & (pl.col("ff_group") == "all")).row(
            0, named=True)
        x = m.filter(f & (pl.col("calib_source") == "calib")).row(0, named=True)
        rows.append({"setting": key, "label": label, "N": N, "anomalies": r["n_attacks"], "detected": r["n_detected"],
                     "onset": r["onset_cov_mean"], "interior": r["interior_cov_mean"], "offset": r["offset_cov_mean"],
                     "onset_rate": r["onset_rate"], "onset_chance": r["onset_chance"],
                     "interior_rate": r["interior_rate"], "interior_chance": r["interior_chance"],
                     "p_normal": r["p_normal"], "roc_auc": x["roc_auc"], "pr_auc": x["pr_auc"], "recall": x["recall"],
                     "fa_per_hour": x["fa_per_hour"]})
    key, label, N, S = LANL
    d = pl.read_csv(P2 / "detections.csv").filter((pl.col("run") == "mv") & (pl.col("score") == "band"))
    fa = pl.read_csv(P2 / "false_alarms.csv").filter((pl.col("run") == "mv") & (pl.col("score") == "band"))
    rows.append({"setting": key, "label": label, "N": N, "anomalies": d.height, "detected": int(d["detected"].sum()),
                 "onset": d["cov_onset"].mean(), "interior": d["cov_interior"].mean(), "offset": d["cov_offset"].mean(),
                 "p_normal": fa["alarms"].sum() / fa["normal_minutes"].sum()})
    return pl.DataFrame(rows, infer_schema_length=None)


def ff_table() -> pl.DataFrame:
    """Forecast Fallback (our interpretation) against plain rolling in each setting where it ran."""
    m = pl.read_csv(P1 / "metrics.csv", infer_schema_length=None)
    s = pl.read_csv(P1 / "segments_summary.csv", infer_schema_length=None)
    rows = []

    def hai(setting, ds, setup, cset, var, exit_, N, note=""):
        f = ((pl.col("dataset") == ds) & (pl.col("model") == MODEL) & (pl.col("setup") == setup)
             & (pl.col("variant") == var) & (pl.col("channel_set") == cset) & (pl.col("score") == "band")
             & (pl.col("agg") == "topk"))
        x = m.filter(f & (pl.col("calib_source") == "calib")).row(0, named=True)
        y = s.filter(f & (pl.col("N") == N) & (pl.col("stratum") == "all") & (pl.col("ff_group") == "all")).row(
            0, named=True)
        rows.append({"setting": setting, "variant": var, "exit": exit_, "status": "finite", "note": note,
                     "fa": x["fa_per_hour"], "fa_unit": "false-alarm steps per normal hour", "roc_auc": x["roc_auc"],
                     "pr_auc": x["pr_auc"], "p_normal": y["p_normal"], "detected": y["n_detected"],
                     "interior": y["interior_cov_mean"]})

    for var, ex, note in (("rolling", "-", "reference"), ("ff-interp-block", "none", ""),
                          ("ff-interp-block-max30", "30 steps", ""),
                          ("ff-interp-block-max60-testinf", "60 steps", "exit set from test knowledge"),
                          ("ff-interp-block-max120", "120 steps", "")):
        hai("HAI 10 s, H = 30 (mv-lit)", "hai2103-10s", "mv-lit", "mvlit34", var, ex, 6, note)
    hai("HAI 1 s, H = 30, history 128", "hai2103-1s", "uni", "uni51", "rolling-c128", "-", 60, "reference")
    for var, ex in (("ff-interp-block-c128", "none"), ("ff-interp-block-max30-c128", "30 steps")):
        rows.append({"setting": "HAI 1 s, H = 30, history 128", "variant": var, "exit": ex,
                     "status": "diverged (non-finite quantiles; REPORT.md 4.19)", "note": ""})
    hai("HAI 1 s, H = 30, history 128", "hai2103-1s", "uni", "uni51", "ff-interp-block-max120-c128", "120 steps", 60)
    fs = pl.read_csv(P2 / "false_alarms_summary.csv")
    fa = pl.read_csv(P2 / "false_alarms.csv")
    d = pl.read_csv(P2 / "detections.csv")
    for run, ex, note in (("mv", "-", "reference"), ("mv-ff", "none", "")):
        k = (pl.col("run") == run) & (pl.col("score") == "band")
        g = fa.filter(k)
        rows.append({"setting": "LANL 1 min, H = 30", "variant": run, "exit": ex, "status": "finite", "note": note,
                     "fa": fs.filter(k)["fa_per_series_day"][0], "fa_unit": "false alarms per series-day",
                     "p_normal": g["alarms"].sum() / g["normal_minutes"].sum(),
                     "detected": int(d.filter(k)["detected"].sum()), "interior": d.filter(k)["cov_interior"].mean()})
    t = pl.DataFrame(rows, infer_schema_length=None)
    ref = t.filter(pl.col("note") == "reference").select("setting", fa_ref="fa")
    return t.join(ref, on="setting", how="left").with_columns(fa_ratio=pl.col("fa") / pl.col("fa_ref"))


def lanl_table() -> pl.DataFrame:
    """Every Phase 2 method on the 144 injections (detections.csv, false_alarms*.csv)."""
    d, fa = pl.read_csv(P2 / "detections.csv"), pl.read_csv(P2 / "false_alarms.csv")
    fs = pl.read_csv(P2 / "false_alarms_summary.csv")
    rows = []
    for run in P2_RUNS:
        k = (pl.col("run") == run) & (pl.col("score") == P2_SCORE.get(run, "band"))
        x, g = d.filter(k), fa.filter(k)
        rows.append({"run": run, "detected": int(x["detected"].sum()), "trials": x.height, "chance": x["chance"].mean(),
                     "onset": x["cov_onset"].mean(), "interior": x["cov_interior"].mean(),
                     "offset": x["cov_offset"].mean(), "fa_per_series_day": fs.filter(k)["fa_per_series_day"][0],
                     "p_normal": g["alarms"].sum() / g["normal_minutes"].sum()})
    return pl.DataFrame(rows)


# ---- figures ----

def _save(fig, name: str) -> None:
    path = OUT / "figures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, metadata={"Date": None})       # no timestamp: reruns are byte-identical
    plt.close(fig)
    print(f"paper: wrote {path}")


def _style() -> None:
    plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "path", "svg.hashsalt": "tsfm-ad", "axes.titlesize": 8.5,
                         "axes.titleweight": "bold", "axes.titlelocation": "left"})


def fig_schematic() -> None:
    """Model-free: which steps of a 20-step anomaly are forecast from a contaminated context, at two strides."""
    fig, axes = plt.subplots(2, 1, figsize=(6.3, 2.5), sharex=True, layout="constrained")
    L, first = 20, {30: 18, 6: 4}         # first origin after the onset, chosen for the drawing
    for ax, S in zip(axes, (30, 6)):
        o0 = first[S] - S * ((first[S] + 40) // S + 1)
        for o in range(o0, 32, S):
            ax.add_patch(plt.Rectangle((o, 0.62), S - 0.25, 0.28, color="#d9d9d9", lw=0))
            ax.plot([o, o], [0.55, 0.97], color="#555555", lw=0.8)
        for t in range(L):
            o = o0 + S * ((t - o0) // S)
            ax.add_patch(plt.Rectangle((t, 0.12), 0.9, 0.3, color=C_CONT if o > 0 else C_CLEAN, lw=0))
        kap = max(0, L - first[S]) / L
        ax.text(L + 1.5, 0.27, rf"$\kappa$ = {kap:.2f}", va="center", fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.set_yticks([0.27, 0.76], ["anomaly steps", f"forecasts, H = S = {S}"])
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.axvline(0, color="black", lw=0.8, ls=":")
        ax.set_title(f"({'a' if S == 30 else 'b'}) a new forecast every {S} steps")
    axes[1].set_xlim(-40, 32)
    axes[1].set_xlabel("steps from the anomaly onset (vertical bars: forecast origins)")
    h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (C_CLEAN, C_CONT)]
    fig.legend(h, ["forecast from a clean context", "forecast from a context that holds the anomaly"],
               loc="outside lower center", ncol=2, frameon=False, fontsize=7.5)
    _save(fig, "fig1_schematic.svg")


def fig_kappa(per: pl.DataFrame, split: pl.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.3, 3.1), layout="constrained")
    r = np.logspace(-1.2, 2.0, 400)
    ax.plot(r, kappa_r(r), color="black", lw=1.2, label=r"expected, random phase: $r/2$ below 1, $1 - 1/(2r)$ above")
    style = {"hai-10s-h30": ("#2f6db5", "o", "HAI 10 s, H = 30"), "hai-10s-h6": ("#d98c1f", "s", "HAI 10 s, H = 6"),
             "hai-1s-c128": ("#2e8b57", "^", "HAI 1 s, H = 30"), "lanl-mv": ("#7a3fbf", "D", "LANL 1 min, H = 30")}
    for key, (c, mk, lab) in style.items():
        g = per.filter(pl.col("setting") == key)
        k = split.filter((pl.col("setting") == key) & (pl.col("method") == "Chronos-2"))["kappa"][0]
        ax.scatter(g["r"], g["kappa_i"], s=11, marker=mk, color=c, alpha=0.6, lw=0,
                   label=rf"{lab}: {g.height} anomalies, pooled $\kappa$ = {k:.3f}")
    ax.set_xscale("log")
    ax.set_xlabel("r = anomaly length / forecast stride")
    ax.set_ylabel("contamination share of the anomaly")
    ax.set_ylim(-0.03, 1.03)
    fig.legend(frameon=False, fontsize=7, loc="outside lower center", ncol=2)
    _save(fig, "fig2_kappa.svg")


def fig_coverage(seg: pl.DataFrame, split: pl.DataFrame) -> None:
    cfv = dict(zip(cf_table()["setting"], cf_table()["c_cf"]))
    sp = split.filter(pl.col("method") == "Chronos-2").sort("kappa")
    order = sp["setting"].to_list()
    labels = [f"{lab}\n" + rf"$\kappa$ = {k:.3f}" for lab, k in zip(sp["label"], sp["kappa"])]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.2), sharey=True, layout="constrained")
    y = np.arange(len(order))[::-1]
    for ax, (a, b, la, lb, ca, cb, title) in zip(axes, (
            ("onset", "interior", "onset", "interior", C_ONSET, C_INT, "(a) coverage by segment"),
            ("c_pre", "c_post", "clean context", "contaminated context", C_CLEAN, C_CONT,
             "(b) coverage by forecast origin"))):
        src = seg if a == "onset" else sp
        for yi, key in zip(y, order):
            row = src.filter(pl.col("setting") == key).row(0, named=True)
            ax.plot([row[a], row[b]], [yi, yi], color="#cccccc", lw=2, zorder=1)
            ax.scatter([row[a]], [yi], color=ca, s=30, zorder=2, label=la if yi == y[0] else None)
            ax.scatter([row[b]], [yi], color=cb, s=30, zorder=2, label=lb if yi == y[0] else None)
            if a == "c_pre" and key in cfv:
                ax.scatter([cfv[key]], [yi], facecolor="white", edgecolor=C_CONT, s=30, zorder=2, lw=1.2,
                           label="contaminated, clean counterfactual" if key == "hai-10s-h30" else None)
        ax.set_title(title)
        ax.set_xlim(-0.02, 0.7)
        ax.set_xlabel("share of steps that alarm")
    h0, l0 = axes[0].get_legend_handles_labels()
    h1, l1 = axes[1].get_legend_handles_labels()
    fig.legend(h0 + h1, l0 + l1, frameon=False, fontsize=7, loc="outside lower center", ncol=5)
    axes[0].set_yticks(y, labels, fontsize=7)
    _save(fig, "fig3_coverage.svg")


def fig_ff(ff: pl.DataFrame) -> None:
    t = ff.filter(pl.col("note") != "reference")
    fig, ax = plt.subplots(figsize=(6.3, 2.6), layout="constrained")
    y = np.arange(t.height)[::-1]
    for yi, r in zip(y, t.iter_rows(named=True)):
        if r["status"] != "finite":
            ax.text(1.05, yi, "diverged: non-finite forecasts, no result", va="center", fontsize=7, color=C_CONT)
            continue
        ax.barh(yi, r["fa_ratio"], color=C_CONT, height=0.6, left=0)
        ax.text(r["fa_ratio"] * 1.08, yi, f"{r['fa_ratio']:.1f}x", va="center", fontsize=7)
    ax.set_xscale("log")
    ax.set_xlim(1, 400)
    ax.axvline(1, color="black", lw=0.8)
    ax.set_yticks(y, [f"{r['setting']}, exit {r['exit']}" for r in t.iter_rows(named=True)],
                  fontsize=7)
    ax.set_xlabel("false alarms of Forecast Fallback / false alarms of plain rolling (log scale)")
    _save(fig, "fig4_ff.svg")


def _fmt(df: pl.DataFrame, digits: dict) -> pl.DataFrame:
    """String columns for the paper's tables (Typst reads the CSVs as they are)."""
    out = df
    for c, d in digits.items():
        out = out.with_columns(pl.col(c).map_elements(lambda v, d=d: f"{v:,.{d}f}", return_dtype=pl.Utf8)
                               .fill_null("-").alias(c))
    return out


def run_paper(cfg: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _style()
    per, split, width = kappa_tables()
    seg, ff, lanl, phase = segments_table(), ff_table(), lanl_table(), phase_table()
    per.write_csv(OUT / "kappa_anomalies.csv")
    split.write_csv(OUT / "origin_split.csv")
    width.write_csv(OUT / "lanl_band_width.csv")
    phase.write_csv(OUT / "grid_phase.csv")
    cf = cf_table()
    cf.write_csv(OUT / "cf_onset_split.csv")
    seg.write_csv(OUT / "segments.csv")
    ff.write_csv(OUT / "ff.csv")
    lanl.write_csv(OUT / "lanl_methods.csv")
    t1 = split.filter(pl.col("method") == "Chronos-2").join(seg.select("setting", "onset", "interior"), on="setting")
    _fmt(t1.select("label", "anomalies", "steps", "kappa_hat", "kappa", "c_pre", "c_post", "coverage", "onset",
                   "interior"),
         {"steps": 0, "kappa_hat": 3, "kappa": 3, "c_pre": 3, "c_post": 3, "coverage": 3, "onset": 3, "interior": 3}
         ).write_csv(OUT / "table_kappa.csv")
    _fmt(seg.filter(pl.col("setting") != "lanl-mv").select("label", "roc_auc", "pr_auc", "recall", "fa_per_hour",
                                                           "detected", "p_normal"),
         {"roc_auc": 3, "pr_auc": 3, "recall": 3, "fa_per_hour": 2, "p_normal": 4}).write_csv(OUT / "table_hai.csv")
    _fmt(split.filter(pl.col("method") == "Chronos-2").select("label", "kappa", "p_band", "c_pre", "c_post", "p_mae",
                                                              "mae_c_pre", "mae_c_post"),
         {"kappa": 3, "p_band": 4, "c_pre": 3, "c_post": 3, "p_mae": 4, "mae_c_pre": 3, "mae_c_post": 3}
         ).write_csv(OUT / "table_scores.csv")
    _fmt(split.filter(pl.col("method") != "Chronos-2").select("label", "method", "kappa", "c_pre", "c_post"),
         {"kappa": 3, "c_pre": 3, "c_post": 3}).write_csv(OUT / "table_split_baselines.csv")
    t = _fmt(ff.select("setting", "note", "exit", "status", "fa", "fa_ratio", "roc_auc", "pr_auc", "p_normal",
                       "detected"), {"fa": 2, "fa_ratio": 1, "roc_auc": 3, "pr_auc": 3, "p_normal": 4})
    t.with_columns(method=pl.when(pl.col("note") == "reference").then(pl.lit("rolling")).otherwise(pl.lit("FF")),
                   fa=pl.when(pl.col("status") == "finite").then("fa").otherwise(pl.lit("diverged")),
                   detected=pl.col("detected").cast(pl.Utf8).fill_null("-")).select(
        "setting", "method", "exit", "fa", "fa_ratio", "roc_auc", "pr_auc", "p_normal", "detected").write_csv(
        OUT / "table_ff.csv")
    _fmt(lanl, {"chance": 2, "onset": 3, "interior": 3, "offset": 3, "fa_per_series_day": 2, "p_normal": 4}
         ).write_csv(OUT / "table_lanl.csv")
    fig_schematic()
    fig_kappa(per, split)
    fig_coverage(seg, split)
    fig_ff(ff)
    print(f"paper: tables in {OUT}")
    try:
        import typst
    except ModuleNotFoundError:
        print("paper: typst not installed, PDF skipped (uv run --extra paper tsfm-ad paper)")
        return
    typst.compile("paper/paper.typ", output="paper/paper.pdf", root=".")
    print("paper: wrote paper/paper.pdf")
