"""Phase 1 figures from the cache and the results CSVs only (PLAN.md section 12, D33, D55, D86).

A method or figure without results is skipped and the reason printed; nothing is dropped silently.
Methods: the base setup's rolling, ff-interp-block, frozen and dual runs plus the three baselines, one fixed colour
each. Scores: band (dual for dual), top-3 mean, `calib` threshold.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import matplotlib.ticker as mticker
import numpy as np
import polars as pl
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from tsfm_ad import data
from tsfm_ad.config import run_key, steps, with_variant
from tsfm_ad.plot_util import (ATTACK, COLORS, INK, MUTED, SEGMENTS, SIGNALS, agg_scores, cf_panel,  # noqa: F401
                               color, current_rows, find_run_dir, hash8_of, headline_score, method_rows, methods,
                               n_rows, origin_panel, plt, read_csv, results_rows, save, shade, threshold, with_keys)
from tsfm_ad.selection import selected

def timeline(cfg: dict, attack_id: str, run_keys: list[tuple[str, dict]], out: Path) -> bool:
    """Signals (z units) with the first run's median and q05-q95 band where the signal is a scored target, and
    each run's aggregated score with its calib threshold, 30 min before onset to 30 min after the end.
    run_keys = methods(cfg, setup): (name, run cfg) pairs, the band run first."""
    att = data.load_attacks(cfg).filter(pl.col("attack_id") == attack_id)
    if att.height == 0 or attack_id not in SIGNALS:
        print(f"plots: timeline {attack_id} skipped, {'no signals fixed' if att.height else 'not in this dataset'}")
        return False
    a = att.row(0, named=True)
    seg = data.load_segment(cfg, a["segment"])
    res, N, pad = cfg["dataset"]["resolution_s"], steps(cfg, cfg["metrics"]["N_onset_s"]), steps(cfg, 1800)
    s, L = a["start_idx"], a["n_steps"]
    lo, hi = max(0, s - pad), min(len(seg), s + L + pad)
    thr_df = read_csv(Path(cfg["paths"]["results"]) / "thresholds.csv", "thresholds")
    band_name, setup = run_keys[0][0], run_keys[0][1]["setup"]
    targets = {c for g in data.setup_groups(cfg, setup) for c in g.targets}
    cs = cfg["channels"]["setups"][setup]["channel_set"]
    panels, skipped = [], []
    for name, c in run_keys:
        rdir, why = find_run_dir(c)
        sc = agg_scores(rdir, cs, headline_score(name)) if rdir else None
        if sc is None:
            skipped.append(f"{name} ({why or f'no scores/{cs}/agg_test.parquet'})")
            continue
        sc = sc.filter((pl.col("file") == seg.name) & pl.col("t").is_between(lo, hi - 1)).sort("t")
        panels.append((name, sc, threshold(thr_df, run_key(c), hash8_of(rdir), cs, headline_score(name)), rdir))
    if skipped:
        print(f"plots: timeline {attack_id}: no scores for " + "; ".join(skipped))
    if not panels:
        print(f"plots: timeline {attack_id} skipped, no method has scores")
        return False
    band, band_path = None, panels[0][3] / "test" / f"{seg.name}.parquet"
    if panels[0][0] == band_name and band_path.exists():
        band = (pl.scan_parquet(band_path).filter(pl.col("t").is_between(lo, hi - 1))
                .select("channel", "t", "q05", "q50", "q95").collect())
    else:
        print(f"plots: timeline {attack_id}: no {band_name} forecast for {seg.name}, signals drawn without a band")
    sig = SIGNALS[attack_id]
    fig, axes = plt.subplots(len(sig) + len(panels), 1, sharex=True, squeeze=False, layout="constrained",
                             figsize=(8, 1.5 * len(sig) + 1.05 * len(panels) + 1),
                             gridspec_kw={"height_ratios": [1.4] * len(sig) + [1] * len(panels)})
    axes, t = axes[:, 0], np.arange(lo, hi)
    for ax, ch in zip(axes, sig):
        shade(ax, L, N, res)
        ax.plot((t - s) * res, seg.rows([ch])[0, lo:hi], color=INK, lw=1.1)
        scored = ch in targets
        if scored and band is not None:
            b = band.filter(pl.col("channel") == ch).sort("t")
            x = (b["t"].to_numpy() - s) * res
            ax.fill_between(x, b["q05"], b["q95"], color=color(band_name), alpha=0.18, lw=0)
            ax.plot(x, b["q50"], color=color(band_name), lw=1.1)
        ax.set_ylabel("z (fit std)")
        ax.set_title(ch + ("" if scored else f"  (not scored in {setup})"), loc="left", pad=2,
                     color=INK if scored else MUTED)
    for ax, (name, sc, thr, _) in zip(axes[len(sig):], panels):
        shade(ax, L, N, res)
        ax.plot((sc["t"].to_numpy() - s) * res, sc["s"], color=color(name), lw=1.2)
        if thr is not None:
            ax.axhline(thr, color=INK, lw=0.9, ls=(0, (4, 2)))
            lt = max(thr, 1e-3)
            ax.set_yscale("symlog", linthresh=lt)
            top = max(float(sc["s"].max() or 0.0), lt)
            ticks = [0.0, thr] + [10.0 ** k for k in range(int(np.floor(np.log10(lt))) + 1,
                                                           int(np.floor(np.log10(top))) + 1) if 10.0 ** k > 1.5 * lt]
            ax.set_yticks(ticks, [f"{v:.3g}" for v in ticks])
            ax.yaxis.set_minor_locator(mticker.NullLocator())
            ax.set_ylim(0, top * 1.3)
        ax.set_title(f"{name}: {headline_score(name)} score, top-3 mean, "
                     + (f"calib threshold {thr:.3g} (dashed; symlog axis)" if thr is not None else
                        "no calib threshold found"), loc="left", pad=2)
        ax.set_ylabel("score")
    axes[-1].set_xlabel("time since attack onset (s)")
    handles = [Line2D([], [], color=INK, lw=1.1, label="observed")]
    if band is not None:
        handles += [Line2D([], [], color=color(band_name), lw=1.1, label=f"median ({setup} {band_name})"),
                    Patch(color=color(band_name), alpha=0.18, label="q05-q95")]
    handles += [Patch(color=ATTACK, alpha=0.25, label=f"onset (first {N * res} s)"),
                Patch(color=ATTACK, alpha=0.10, label="interior"),
                Patch(color=MUTED, alpha=0.15, label=f"offset ({N * res} s after end)")]
    head = f"{attack_id}: {a['processes']}, {a['duration_s']} s, {seg.name}; {run_key(run_keys[0][1]).model}"
    fig.legend(handles=handles, loc="outside upper left", ncol=3, title=head, alignment="left", title_fontsize=10)
    return save(fig, out)



def boundary_bars(summary_csv: Path, out: Path, run_keys=(), channel_set: str = "", N: int = 6,
                  N_s: int = 60) -> bool:
    """Mean coverage per segment (top) and any-alarm rate per segment with its chance level (bottom)."""
    df = read_csv(Path(summary_csv), "boundary_interior.png")
    if df is None:
        return False
    df = n_rows(df.filter((pl.col("stratum") == "all") & (pl.col("ff_group") == "all")), N, N_s)
    rows = method_rows(df, run_keys, channel_set)
    if not rows:
        print("plots: boundary_interior.png skipped, no method has rows")
        return False
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.2), sharex=True, layout="constrained")
    w = 0.8 / len(rows)
    for i, (name, r) in enumerate(rows):
        x, r = np.arange(len(SEGMENTS)) - 0.4 + w * (i + 0.5), r.row(-1, named=True)
        a1.bar(x, [r[f"{s}_cov_mean"] for s in SEGMENTS], w * 0.9, color=color(name), label=name)
        a2.bar(x, [r[f"{s}_rate"] for s in SEGMENTS], w * 0.9, color=color(name))
        a2.scatter(x, [r[f"{s}_chance"] for s in SEGMENTS], marker="_", s=90, color=INK, lw=1.4, zorder=3,
                   label="chance level 1-(1-p)^n" if i == 0 else None)
    a1.set_ylabel("mean coverage\n(share of segment steps alarmed)")
    a2.set_ylabel("detection rate\n(attacks with any alarm)")
    a2.set_xticks(np.arange(len(SEGMENTS)), SEGMENTS)
    for a in (a1, a2):
        a.set_ylim(0, 1)
        a.grid(axis="x", visible=False)
    rk = run_key(run_keys[0][1])
    head = (f"Boundary vs interior: {rk.dataset}, {rk.model}, {rk.setup} on {channel_set}, N = {N} steps\n"
            "band score (dual score for dual), top-3 mean, calib threshold")
    fig.legend(handles=a1.get_legend_handles_labels()[0] + a2.get_legend_handles_labels()[0],
               loc="outside upper left", ncol=4, title=head, alignment="left", title_fontsize=10)
    return save(fig, out)



def boundary_origin(by_h_csv: Path, cf_csv: Path, out: Path, cfg: dict, run_keys, channel_set: str, N: int,
                    N_s: int) -> bool:
    """Interior coverage by forecast origin side (pre / post onset) within each h bucket, one panel per method;
    below, the cf-onset vs rolling contrast of each setup in cf_onset.csv."""
    byh, cf = read_csv(Path(by_h_csv), "origin panels"), read_csv(Path(cf_csv), "cf-onset panel")
    rows, cf_sets = [], []
    if byh is not None:
        byh = n_rows(byh.filter(pl.col("segment") == "interior"), N, N_s)
        if "all" in byh["tso_bucket"].cast(pl.String).to_list():   # pooled rows given: never double count
            byh = byh.filter(pl.col("tso_bucket").cast(pl.String) == "all")
        rows = method_rows(byh, run_keys, channel_set)
    if cf is not None:
        rk = run_key(with_variant(run_keys[0][1], "rolling"))
        names = [rk.variant, run_key(with_variant(run_keys[0][1], "cf-onset")).variant]
        cf = current_rows(with_keys(cf).filter(
            (pl.col("dataset") == rk.dataset) & (pl.col("model") == rk.model) & pl.col("variant").is_in(names)
            & (pl.col("score") == "band") & (pl.col("agg") == "topk") & (pl.col("segment") == "interior")), cfg)
        sets = {su: spec["channel_set"] for su, spec in cfg["channels"]["setups"].items()}
        cf_sets = [(su, g) for (su, cs), g in cf.group_by("setup", "channel_set", maintain_order=True)
                   if sets.get(su) == cs]
        if not cf_sets:
            print("plots: cf_onset.csv has no interior rows for this dataset and model; cf panel skipped")
    if not rows and not cf_sets:
        print("plots: boundary_interior_origin.png skipped, no data")
        return False
    ncol, nrow = 3, -(-len(rows) // 3)
    fig = plt.figure(figsize=(8, 2.4 * nrow + (2.8 if cf_sets else 0) + 0.6), layout="constrained")
    top, bottom = fig.subfigures(2, 1, height_ratios=[2.4 * nrow, 2.8]) if rows and cf_sets else (fig, fig)
    if rows:
        axes = top.subplots(nrow, ncol, sharey=True, squeeze=False).ravel()
        for ax, (name, r) in zip(axes, rows):
            origin_panel(ax, name, r)
        for ax in axes[len(rows):]:
            ax.set_visible(False)
        for ax in axes[::ncol]:
            ax.set_ylabel("interior coverage")
        top.suptitle(f"Interior coverage by forecast origin on {channel_set}, N = {N} steps: light = pre-onset "
                     "origin (clean context), solid = post-onset origin (context holds attack data); "
                     "under each bucket: scored steps pre | post", x=0.01, ha="left", fontsize=9, wrap=True)
    if cf_sets:
        for ax, (su, g) in zip(bottom.subplots(1, len(cf_sets), squeeze=False).ravel(), cf_sets):
            cf_panel(ax, su, g)
    return save(fig, out)


def size_latency(csv: Path, out: Path, dataset: str | None = None, cfg: dict | None = None) -> bool:
    """ROC-AUC and PR-AUC vs median seconds per forecast call, one line per (setup, variant) across sizes. With cfg,
    only rows whose run still has their hash8 are drawn (D114)."""
    df = read_csv(Path(csv), "size_latency.png")
    if df is not None and dataset and "dataset" in df.columns:
        df = df.filter(pl.col("dataset") == dataset)
    if df is not None and cfg is not None:
        df = current_rows(df, cfg)
    if df is None or df.height == 0:
        print(f"plots: size_latency.png skipped, no rows{f' for {dataset}' if dataset else ''}")
        return False
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), sharex=True, layout="constrained")
    for (setup, variant, sel), g in df.group_by("setup", "variant", "selected", maintain_order=True):
        g, sel = g.sort("params" if "params" in g.columns else "sec_per_call_median"), str(sel).lower() == "true"
        label = f"{setup} {variant} ({'selected on test results' if sel else 'unselected'})"
        for ax, m in zip(axes, ("roc_auc", "pr_auc")):
            ax.plot(g["sec_per_call_median"], g[m], color=color(variant), lw=1.4, ls="-" if sel else "--",
                    marker="o" if sel else "s", ms=6, label=label)
            for x, y, mod, n in zip(g["sec_per_call_median"], g[m], g["model"], g["params"]):
                size = next((p for p in str(mod).split("-") if re.fullmatch(r"\d+M", p)), f"{int(n) / 1e6:.0f}M")
                ax.annotate(size, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=7.5, color=MUTED)
    for ax, m in zip(axes, ("ROC-AUC", "PR-AUC")):
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(mticker.LogLocator(subs=(1, 2, 5)))
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_formatter(mticker.NullFormatter())
        ax.set_xlabel("seconds per forecast call (median, log scale)")
        ax.set_ylabel(f"test {m}")
    fig.legend(handles=axes[0].get_legend_handles_labels()[0], loc="outside upper left")
    return save(fig, out)


def _base_setup(cfg: dict) -> str:
    try:
        s, src = selected("base", Path(cfg["paths"]["results"]) / "selection.csv")["setup"], "selection.csv"
    except (FileNotFoundError, LookupError):
        if cfg["setup"] == "selected":
            raise
        s, src = cfg["setup"], "the config (no base selection yet)"
    print(f"plots: base setup {s}, from {src}")
    return s


def figures_dir(cfg: dict) -> Path:
    """<results>/figures for 10 s runs; <results>/figures/<dataset> otherwise, so 1 s figures never overwrite them."""
    out = Path(cfg["paths"]["results"]) / "figures"
    return out if cfg["dataset"]["resolution_s"] == 10 else out / cfg["dataset"]["key"]


def run_plots(cfg: dict, setup: str | None = None) -> None:
    """Every figure of PLAN.md section 12 into figures_dir(cfg). `setup` defaults to the base pick (or cfg.setup)."""
    res = Path(cfg["paths"]["results"])
    out = figures_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    setup = setup or _base_setup(cfg)
    runs = methods(cfg, setup)
    cs, N_s = cfg["channels"]["setups"][setup]["channel_set"], cfg["metrics"]["N_onset_s"]
    N = steps(cfg, N_s)
    for a in cfg["plots"]["timeline_attacks"]:
        timeline(cfg, a, runs, out / f"timeline_{a}.png")
    ff60 = copy.deepcopy(runs[1][1])
    ff60["variant"]["ff"]["max_duration"] = 60
    bar_runs = runs[:2] + [("ff-interp-block-max60-testinf", ff60)] + runs[2:]
    boundary_bars(res / "segments_summary.csv", out / "boundary_interior.png", bar_runs, cs, N, N_s)
    boundary_origin(res / "segments_by_h.csv", res / "cf_onset.csv", out / "boundary_interior_origin.png", cfg,
                    bar_runs, cs, N, N_s)
    size_latency(res / "size_latency.csv", out / "size_latency.png", cfg["dataset"]["key"], cfg)
