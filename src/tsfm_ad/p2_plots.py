"""Phase 2 figures from results/phase2 and the cache only (PLAN.md 15.6): detection curves per injection type and
duration, false alarms per run, and one example timeline per type."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from tsfm_ad import p2, p2_eval  # noqa: E402

RUN_STYLE = {"mv": ("#1f5fbf", "-", "o"), "mv-cov": ("#7a3fbf", "-", "s"), "mv-ff": ("#c0392b", "--", "v"),
             "mv-frozen": ("#2e8b57", "--", "^"), "mv-dual": ("#8a8a8a", ":", "D"),
             "lastvalue": ("#d98c1f", "-.", "<"), "seasonal-naive": ("#b5651d", "-.", ">"),
             "robustz": ("#555555", "-.", "x")}
HEADLINE = {"mv-dual": "dual"}            # every other run on the band score


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"p2 plots: wrote {path}")


def curves(res: Path) -> None:
    c = pl.read_csv(res / "curves.csv")
    types = [t for t in ("silence", "burst", "ramp", "shift") if t in set(c["type"].to_list())]
    durs = {t: sorted(c.filter(pl.col("type") == t)["duration_min"].unique().to_list()) for t in types}
    fig, axes = plt.subplots(2, len(types), figsize=(3.5 * len(types) + 1, 6.4), sharey=True, layout="constrained",
                             squeeze=False)
    for j, t in enumerate(types):
        for i, d in enumerate(durs[t][:2]):
            ax = axes[i, j]
            for run, (col, ls, mk) in RUN_STYLE.items():
                g = c.filter((pl.col("run") == run) & (pl.col("score") == HEADLINE.get(run, "band"))
                             & (pl.col("type") == t) & (pl.col("duration_min") == d)).sort("magnitude")
                if g.height:
                    ax.plot(g["magnitude"], g["rate"], color=col, ls=ls, marker=mk, ms=4, lw=1.3, label=run)
                if run == "mv" and g.height and "chance_mean" in g.columns:      # D151
                    ax.fill_between(g["magnitude"], 0, g["chance_mean"], color=col, alpha=0.12, lw=0,
                                    label="mv chance (false alarms alone)")
            ax.set_title(f"{t}, {d} min", fontsize=10)
            ax.set_ylim(-0.03, 1.03)
            ax.set_xlabel({"silence": "kept fraction of normal", "burst": "k x local baseline",
                           "ramp": "end level (+ x normal)", "shift": "step (+ x normal)"}[t], fontsize=8)
            if t in ("burst", "ramp"):
                ax.set_xscale("log")
                m = sorted(c.filter(pl.col("type") == t)["magnitude"].unique().to_list())
                ax.set_xticks(m, [f"{v:g}" for v in m])
                ax.minorticks_off()
            if j == 0:
                ax.set_ylabel("detection rate")
    axes[0, 0].legend(fontsize=7, loc="lower left")
    fig.suptitle("Phase 2: detection rate per injection (6 trials per point; band score, dual for mv-dual; "
                 "calib 99.5th percentile per series)", fontsize=10)
    _save(fig, res / "figures" / "detection_curves.png")


def false_alarms(res: Path) -> None:
    f = pl.read_csv(res / "false_alarms_summary.csv")
    f = f.filter(pl.col("score") == pl.col("run").replace_strict(HEADLINE, default="band"))
    fig, ax = plt.subplots(figsize=(7, 3.2), layout="constrained")
    runs = [r for r in RUN_STYLE if r in f["run"].to_list()]
    vals = [f.filter(pl.col("run") == r)["fa_per_series_day"].item() for r in runs]
    ax.bar(runs, vals, color=[RUN_STYLE[r][0] for r in runs])
    ax.axhline(0.005 * 1440, color="black", lw=0.8, ls=":", label="calib rate by construction (7.2 per day)")
    ax.set_ylabel("false alarms per series-day")
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", labelsize=8, rotation=20)
    _save(fig, res / "figures" / "false_alarms.png")


def timelines(cfg: dict, res: Path) -> None:
    """One injection per type (the largest magnitude, longest duration, seed 0): the series, the mv and frozen
    bands, and the mv band score against its threshold."""
    data = p2.Data(cfg)
    man = pl.read_csv(res / "injections.csv").filter(pl.col("seed") == cfg["inject"]["seeds"][0])
    thr = pl.read_csv(res / "thresholds.csv").filter((pl.col("run") == "mv") & (pl.col("score") == "band"))
    thr = dict(zip(thr["series"], thr["threshold"]))
    seed = cfg["inject"]["seeds"][0]
    mv = p2.read(cfg, "mv", f"seed{seed}", data)
    try:
        fr = p2.read(cfg, "mv-frozen", f"seed{seed}", data)
    except FileNotFoundError:
        fr = None
    types = [t for t in ("silence", "burst", "ramp", "shift") if t in set(man["type"].to_list())]
    fig, axes = plt.subplots(2, len(types), figsize=(3.75 * len(types) + 0.5, 5.6), layout="constrained",
                             sharex="col", gridspec_kw={"height_ratios": [2, 1]}, squeeze=False)
    for j, t in enumerate(types):
        g = man.filter(pl.col("type") == t).sort(["magnitude", "duration_min"], descending=True)
        if not g.height:
            continue
        r = g.row(0, named=True)
        pad = max(240, r["duration_min"])
        lo, hi = r["start"] - pad, r["end"] + pad
        x = mv.filter((pl.col("series") == r["series"]) & (pl.col("t") >= lo) & (pl.col("t") < hi)).sort("t")
        tt = (x["t"].to_numpy() - r["start"]) / 60
        ax = axes[0, j]
        ax.plot(tt, x["y"], color="black", lw=0.7, label="observed (z of log1p)")
        ax.fill_between(tt, x["q05"], x["q95"], color="#1f5fbf", alpha=0.25, label="mv q05-q95")
        if fr is not None:
            y = fr.filter((pl.col("series") == r["series"]) & (pl.col("t") >= lo) & (pl.col("t") < hi)).sort("t")
            ax.plot(tt, y["q05"], color="#2e8b57", lw=0.7, ls="--", label="frozen q05 / q95")
            ax.plot(tt, y["q95"], color="#2e8b57", lw=0.7, ls="--")
        ax.axvspan(0, r["duration_min"] / 60, color="#c0392b", alpha=0.10)
        ax.set_title(f"{t} on {r['series']}: magnitude {r['magnitude']:g}, {r['duration_min']} min", fontsize=9)
        sc = p2_eval.scored(x, cfg["score"]["eps"])
        axes[1, j].plot(tt, sc["band"], color="#1f5fbf", lw=0.8)
        axes[1, j].axhline(thr[r["series"]], color="black", ls="--", lw=0.8)
        axes[1, j].axvspan(0, r["duration_min"] / 60, color="#c0392b", alpha=0.10)
        axes[1, j].set_yscale("symlog", linthresh=1)
        axes[1, j].set_xlabel("hours from injection start")
    axes[0, 0].legend(fontsize=7, loc="lower left")
    axes[1, 0].set_ylabel("mv band score")
    _save(fig, res / "figures" / "timelines.png")


def run_plots(cfg: dict) -> None:
    res = Path(cfg["paths"]["results"])
    curves(res)
    false_alarms(res)
    timelines(cfg, res)
