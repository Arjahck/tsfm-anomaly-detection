"""The restart-rate figure (D154): one HAI attack forecast every 5 minutes (H = 30, the headline) and every minute
(H = 6, option B), from the cache and results only. A402 is picked from the per-attack results to illustrate
REPORT.md 4.20 (an illustration, not a result); the numbers for all 50 attacks are in the panel titles."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from tsfm_ad import data
from tsfm_ad.config import load_config, steps, with_variant
from tsfm_ad.plot_util import ATTACK, INK, MUTED, find_run_dir, hash8_of, plt, read_csv, shade

ATTACK_ID, CHANNEL, CS = "A402", "P1_PCV02Z", "uni51"
RUNS = (("every 5 minutes (H = 30)", "configs/exp1_uni.yaml"),
        ("every minute (H = 6)", "configs/res10s_uni_h6.yaml"))
BAND, ALARM, INSIDE = "#2a78d6", "#0b0b0b", "#b3261e"


def _row(df: pl.DataFrame, hash8: str, **eq) -> dict:
    df = df.filter(pl.col("hash8") == hash8)
    for k, v in eq.items():
        df = df.filter(pl.col(k).cast(pl.String) == str(v))
    if df.height != 1:
        raise LookupError(f"{df.height} rows for {hash8} {eq}")
    return df.row(0, named=True)


def run(config: str = "configs/exp1_uni.yaml") -> bool:
    cfg = load_config(config)
    res_dir = Path(cfg["paths"]["results"])
    res, N = cfg["dataset"]["resolution_s"], steps(cfg, cfg["metrics"]["N_onset_s"])
    a = data.load_attacks(cfg).filter(pl.col("attack_id") == ATTACK_ID).row(0, named=True)
    s, L, pad = a["start_idx"], a["n_steps"], steps(cfg, 600)
    lo, hi = s - pad, s + L + pad
    seg = data.load_segment(cfg, a["segment"])
    y = seg.Z[seg.channels.index(CHANNEL), lo:hi]
    minutes = lambda idx: (np.asarray(idx) - s) * res / 60
    thr, met = read_csv(res_dir / "thresholds.csv", "thresholds"), read_csv(res_dir / "metrics.csv", "metrics")
    summ = read_csv(res_dir / "segments_summary.csv", "segments_summary")
    per = read_csv(res_dir / "segments_per_attack.csv", "segments_per_attack")
    fig = plt.figure(figsize=(10, 10.4), layout="constrained")
    gs = fig.add_gridspec(5, 1, height_ratios=[1.0, 1.4, 1, 1.4, 1])
    head = fig.add_subplot(gs[0])
    head.axis("off")
    axes = [fig.add_subplot(gs[1])]
    axes += [fig.add_subplot(gs[i], sharex=axes[0]) for i in (2, 3, 4)]
    for x in axes[:-1]:
        x.tick_params(labelbottom=False)
    for k, (label, path) in enumerate(RUNS):
        rdir, why = find_run_dir(with_variant(load_config(path), "rolling"))
        if rdir is None:
            raise FileNotFoundError(why)
        h8, key = hash8_of(rdir), {"channel_set": CS, "score": "band", "agg": "topk"}
        band = (pl.scan_parquet(rdir / "test" / f"{seg.name}.parquet")
                .filter((pl.col("channel") == CHANNEL) & pl.col("t").is_between(lo, hi - 1))
                .select("t", "origin", "q05", "q50", "q95").collect().sort("t"))
        sc = (pl.scan_parquet(rdir / "scores" / CS / "agg_test.parquet")
              .filter((pl.col("file") == seg.name) & pl.col("t").is_between(lo, hi - 1))
              .select("t", "band_topk").collect().sort("t"))
        th = _row(thr, h8, calib_source="calib", **key)["threshold"]
        fa = _row(met, h8, calib_source="calib", **key)["fa_per_hour"]
        al = _row(summ, h8, N=N, stratum="all", ff_group="all", **key)
        one = _row(per, h8, N=N, attack_id=ATTACK_ID, **key)
        post = int(one["n_post_origin"])
        ax, axs = axes[2 * k], axes[2 * k + 1]
        for x in (ax, axs):
            shade(x, L, N, res / 60)
        for o in band["origin"].unique().sort().to_list():
            inside = s < o < s + L
            for x in (ax, axs):
                x.axvline(minutes(o), color=INSIDE if inside else MUTED, lw=1.3 if inside else 0.6,
                          ls="-" if inside else (0, (2, 3)), alpha=0.9 if inside else 0.6)
        ax.plot(minutes(np.arange(lo, hi)), y, color=INK, lw=1.1)
        bt = minutes(band["t"].to_numpy())
        ax.fill_between(bt, band["q05"], band["q95"], color=BAND, alpha=0.22, lw=0)
        ax.plot(bt, band["q50"], color=BAND, lw=1.0)
        top = 2 * max(float(band["q50"].max()), float(np.percentile(y, 90)))
        ax.set_ylim(min(float(y.min()), float(band["q05"].min()), 0) - 0.05 * top, top)
        if y.max() > top:
            ax.text(minutes(lo + int(np.argmax(y))) + 0.15, 0.9 * top, f"spike to {y.max():.0f}, off scale",
                    fontsize=8, color=MUTED, va="top")
        pre, inner = float(np.median(y[:pad])), float(np.median(y[pad:pad + L]))
        q50, bts = band["q50"].to_numpy(), band["t"].to_numpy()
        caught = np.flatnonzero((bts > s) & (bts < s + L) & (np.abs(q50 - inner) < np.abs(q50 - pre)))
        if caught.size:
            xc = minutes(bts[caught[0]])
            ax.annotate("the forecast now takes the attack level as normal", xy=(xc, q50[caught[0]]),
                        xytext=(xc + 3.5, 0.62 * top), fontsize=8.5, color=BAND,
                        arrowprops={"arrowstyle": "->", "color": BAND, "lw": 0.9})
        else:
            ax.annotate("the forecast still expects the level from before the attack", xy=(minutes(s + L // 2), pre),
                        xytext=(minutes(s + L // 2) + 2.5, 0.05 * top), fontsize=8.5, color=BAND,
                        arrowprops={"arrowstyle": "->", "color": BAND, "lw": 0.9})
        ax.set_ylabel(f"{CHANNEL}\nz (fit std)")
        ax.set_title(f"A new forecast {label}: {post} of {L} attack steps forecast from a context "
                     "that holds the attack",
                     loc="left", fontsize=10, fontweight="bold", color=INK)
        st = sc["band_topk"].to_numpy()
        tt = minutes(sc["t"].to_numpy())
        axs.plot(tt, st, color=MUTED, lw=1.1)
        hit = st > th
        axs.scatter(tt[hit], st[hit], s=14, color=ALARM, zorder=3)
        axs.axhline(th, color=INK, lw=0.9, ls=(0, (4, 2)))
        axs.set_yscale("symlog", linthresh=th)
        axs.set_ylim(0, max(float(st.max()), th) * 2)
        axs.set_yticks([0, th], ["0", f"{th:.1f}"])
        axs.set_ylabel("band score")
        axs.set_title(f"Share of steps that alarm.  This attack: onset {one['onset_cov']:.2f} · interior "
                      f"{one['interior_cov']:.2f} · offset {one['offset_cov']:.2f}.  All 50 attacks: onset "
                      f"{al['onset_cov_mean']:.3f} · interior {al['interior_cov_mean']:.3f}\nFalse alarms on normal "
                      f"data: {fa:.2f} steps per hour ({al['p_normal'] * 100:.2f} % of normal steps)",
                      loc="left", fontsize=8.5, color=INK)
    axes[-1].set_xlabel("minutes since attack onset")
    handles = [Line2D([], [], color=INK, lw=1.1, label="observed"),
               Line2D([], [], color=BAND, lw=1.0, label="forecast median"),
               Patch(color=BAND, alpha=0.22, label="forecast band (q05-q95)"),
               Line2D([], [], color=MUTED, lw=0.6, ls=(0, (2, 3)), label="new forecast starts"),
               Line2D([], [], color=INSIDE, lw=1.3, label="new forecast starts inside the attack"),
               Patch(color=ATTACK, alpha=0.25, label=f"onset (first {N * res} s)"),
               Patch(color=ATTACK, alpha=0.10, label="interior"),
               Patch(color=MUTED, alpha=0.15, label=f"offset ({N * res} s after the end)"),
               Line2D([], [], color=MUTED, lw=1.1, label="band score, top-3 channels"),
               Line2D([], [], color=INK, lw=0.9, ls=(0, (4, 2)), label="threshold (calib, 99.5th pct)"),
               Line2D([], [], color=ALARM, marker="o", ls="", ms=4, label="alarm")]
    t1 = head.text(0, 1, "The interior goes quiet only when most forecasts start inside the attack", fontsize=13,
              fontweight="bold", color=INK, va="top", transform=head.transAxes)
    t2 = head.text(0, 0.78, f"HAI attack {ATTACK_ID} ({a['duration_s']} s, valve PCV02 in P1), Chronos-2, one channel at a "
              "time.\nSame model, data and threshold rule: only how often a new forecast starts changes.",
              fontsize=9, color=MUTED, va="top", transform=head.transAxes)
    lg = head.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, -0.05), ncol=4, fontsize=8.5)
    for art in (t1, t2, lg):
        art.set_in_layout(False)                 # the header may run wider than the axes; the plots keep full width
    out = Path(cfg["paths"]["results"]) / "figures" / "restart_timeline.png"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"plots: wrote {out}")
    return True
