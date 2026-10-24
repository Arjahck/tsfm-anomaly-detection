"""Shared pieces of the Phase 1 figures: style and colours, method list, run-directory lookup, results rows,
and the panels of boundary_interior_origin.png (PLAN.md section 12, D55, D86, D114). Cache and results only."""
from __future__ import annotations

import copy
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

from tsfm_ad import baselines, cache, context  # noqa: E402
from tsfm_ad.config import run_key, with_variant  # noqa: E402
from tsfm_ad.selection import run_cfg, with_keys  # noqa: E402

COLORS = {"rolling": "#2a78d6", "ff-interp-block": "#eb6834", "frozen": "#1baf7a", "dual": "#eda100",
          "robustz": "#e87ba4", "lastvalue": "#008300", "seasonal-refday": "#6250d6",
          "ff-interp-block-max60-testinf": "#e34948", "cf-onset": "#52514e"}
INK, MUTED, GRID, ATTACK = "#0b0b0b", "#52514e", "#e1e0d9", "#d03b3b"
SEGMENTS = ("onset", "interior", "interior_eq", "offset")
# D55: fixed from the PDF control loops (HAI-PDF p.8, 11, 12, 15); A101 (the smoke attack) uses the P1-PC loop
SIGNALS = {"A202": ["P1_PIT01", "P1_PCV01D", "P1_B2016"], "A210": ["P1_PIT01", "P1_PCV01D"],
           "A403": ["P1_LIT01", "P1_LCV01D", "P3_LIT01"], "A217": ["P2_SIT01", "P2_VYT02"],
           "A219": ["P3_LIT01", "P3_LCP01D"], "A203": ["P1_LIT01", "P1_LCV01D"],
           "A101": ["P1_PIT01", "P1_PCV01D", "P1_B2016"]}
plt.rcParams.update({"font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8,
                     "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "savefig.dpi": 150,
                     "legend.frameon": False})


def color(name: str) -> str:
    return COLORS.get(re.sub(r"-c\d+$", "", name), MUTED)


def headline_score(name: str) -> str:
    return "dual" if name == "dual" else "band"


def methods(cfg: dict, setup: str) -> list[tuple[str, dict]]:
    """(method name, run cfg) for the TSFM variants of `setup` and the three baselines."""
    c = copy.deepcopy(cfg)
    c["setup"] = setup
    tsfm = [("rolling", "rolling"), ("ff-interp-block", "ff"), ("frozen", "frozen"), ("dual", "dual")]
    return [(n, with_variant(c, k)) for n, k in tsfm] + [(b, baselines.baseline_cfg(c, b)) for b in baselines.BASELINES]


def find_run_dir(c: dict) -> tuple[Path | None, str]:
    """The current cache directory of a run (hash recomputed from config and code), or None and the reason."""
    try:
        d = cache.run_dir(c, extra=context.ff_extra(c))
    except FileNotFoundError as e:
        return None, str(e)
    return (d, "") if d.exists() else (None, f"{d} does not exist")


def agg_scores(rdir: Path, channel_set: str, score: str, agg: str = "topk", split: str = "test"):
    """(file, t, s) of one aggregated score from <run>/scores/<channel_set>/agg_<split>.parquet, which holds either
    a column `<score>_<agg>` or long columns score, agg, value. None if the file does not exist."""
    path = rdir / "scores" / channel_set / f"agg_{split}.parquet"
    if not path.exists():
        return None
    df = pl.read_parquet(path)
    if f"{score}_{agg}" in df.columns:
        return df.select("file", "t", pl.col(f"{score}_{agg}").alias("s"))
    if {"score", "agg", "value"} <= set(df.columns):
        df = df.filter((pl.col("score") == score) & (pl.col("agg") == agg))
        return df.select("file", "t", pl.col("value").alias("s"))
    raise ValueError(f"{path} has neither a {score}_{agg} column nor score/agg/value columns")


def hash8_of(d: Path) -> str:
    return d.name.split("@")[-1]


def results_rows(df: pl.DataFrame, rk, hash8: str, **eq) -> pl.DataFrame:
    """Rows of a results frame for one run key at its current hash8 (and column == value filters). Rows of any
    other hash are never used (D114)."""
    return with_keys(df).filter(*[pl.col(k) == v for k, v in zip(("dataset", "model", "setup", "variant"), rk)],
                                pl.col("hash8").cast(pl.String) == hash8,
                                *[pl.col(k).cast(pl.String) == str(v) for k, v in eq.items() if k in df.columns])


def threshold(thr: pl.DataFrame | None, rk, hash8: str, channel_set: str, score: str,
              agg: str = "topk") -> float | None:
    if thr is None:
        return None
    rows = results_rows(thr, rk, hash8, channel_set=channel_set, score=score, agg=agg, calib_source="calib")
    if "smooth" in rows.columns:
        rows = rows.filter(pl.col("smooth").is_null() | (pl.col("smooth").cast(pl.String) == ""))
    return float(rows["threshold"][-1]) if rows.height else None


def read_csv(path: Path, what: str) -> pl.DataFrame | None:
    if not path.exists():
        print(f"plots: {what} skipped, {path} does not exist")
        return None
    return pl.read_csv(path, infer_schema_length=None, schema_overrides={"hash8": pl.String})   # never a number


def save(fig, out: Path) -> bool:
    fig.savefig(out)
    plt.close(fig)
    print(f"plots: wrote {out}")
    return True


def shade(ax, L: int, N: int, res: int) -> None:
    """Attack window (onset = first N steps, interior = the rest) and the offset (N steps after the end)."""
    on = min(N, L) * res
    ax.axvspan(0, on, color=ATTACK, alpha=0.25, lw=0)
    ax.axvspan(on, L * res, color=ATTACK, alpha=0.10, lw=0)
    ax.axvspan(L * res, (L + N) * res, color=MUTED, alpha=0.15, lw=0)



def method_rows(df: pl.DataFrame, run_keys, channel_set: str, **eq) -> list[tuple[str, pl.DataFrame]]:
    """(name, rows) of each method that has rows at the current hash of its run directory; the others printed."""
    out, missing = [], []
    for name, c in run_keys:
        d, why = find_run_dir(c)
        rows = None if d is None else results_rows(df, run_key(c), hash8_of(d), channel_set=channel_set,
                                                   score=headline_score(name), agg="topk", **eq)
        if rows is not None and rows.height:
            out.append((name, rows))
        else:
            missing.append(f"{name} ({why or f'no rows at the current hash {hash8_of(d)}'})")
    if missing:
        print(f"plots: on {channel_set}, skipped " + "; ".join(missing))
    return out


def current_rows(df: pl.DataFrame, cfg: dict) -> pl.DataFrame:
    """Rows of a results frame whose TSFM run (rebuilt from run_key) still has their hash8; others printed."""
    df = with_keys(df).with_columns(pl.col("hash8").cast(pl.String))
    ok = []
    for rk, h in df.select("run_key", "hash8").unique(maintain_order=True).iter_rows():
        try:
            d, why = find_run_dir(run_cfg(cfg, rk))
        except ValueError as e:
            d, why = None, str(e)
        if d is not None and hash8_of(d) == h:
            ok.append(rk + "@" + h)
        else:
            print(f"plots: rows of {rk}@{h} skipped, {why or f'its current hash is {hash8_of(d)}'}")
    return df.filter(pl.concat_str("run_key", pl.lit("@"), "hash8").is_in(ok))


def n_rows(df: pl.DataFrame, N: int, N_s: int) -> pl.DataFrame:
    """Rows at the headline N (the CSV may give N in steps or in seconds)."""
    return df.filter(pl.col("N") == (N if N in set(df["N"].to_list()) else N_s))



def wmean(df: pl.DataFrame, val: str, w: str) -> tuple[float, int]:
    d = df.filter(pl.col(val).is_not_null() & pl.col(val).is_not_nan() & (pl.col(w) > 0))
    n = int(d[w].sum()) if d.height else 0
    return (float((d[val] * d[w]).sum() / n) if n else 0.0), n


def origin_panel(ax, name: str, r: pl.DataFrame) -> None:
    """Coverage of pre-onset (light) and post-onset (solid) origins per h bucket; scored steps under the ticks."""
    buckets = sorted(r["h_bucket"].unique().to_list(), key=lambda b: int(re.findall(r"\d+", str(b))[0]))
    ticks = []
    for i, b in enumerate(buckets):
        ns = []
        for side, dx, alpha in (("pre", -0.2, 0.35), ("post", 0.2, 1.0)):
            v, n = wmean(r.filter((pl.col("h_bucket") == b) & (pl.col("origin_side") == side)), "coverage", "n_steps")
            ax.bar(i + dx, v, 0.38, color=color(name), alpha=alpha)
            ns.append(str(n))
        ticks.append(f"h {b}\n{' | '.join(ns)}")
    ax.set_xticks(range(len(buckets)), ticks, fontsize=7.5)
    ax.set_title(name, loc="left")
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)


def cf_panel(ax, setup: str, g: pl.DataFrame) -> None:
    """Step-weighted mean score of interior steps, rolling vs cf-onset, by the rolling step's origin side."""
    ticks, top = [], 0.0
    for i, (side, suf, w) in enumerate([("pre", "", "n_steps"), ("post", "", "n_steps"),
                                        ("post", "_hcf_le30", "n_hcf_le30")]):
        gs = g.filter(pl.col("origin_side") == side)
        for dx, lab, col in ((-0.2, "rolling", "score_rolling_mean"), (0.2, "cf-onset", "score_cf_mean")):
            v, n = wmean(gs, col + suf, w)
            ax.bar(i + dx, v, 0.38, color=color(lab), label=lab if i == 0 else None)
            top = max(top, v)
        ticks.append(f"{side}-onset origin" + (", cf h <= 30" if suf else "") + f"\n{n} steps")
    ax.set_xticks(range(3), ticks, fontsize=7.5)
    ax.set_ylim(0, top * 1.3 or 1)
    ax.set_ylabel("mean band score\n(top-3, interior steps)")
    ax.set_title(f"cf-onset (clean context from onset) vs rolling: {setup}", loc="left")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncol=2)
