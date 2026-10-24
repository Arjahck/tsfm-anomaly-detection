"""Cross-method summaries and the cf-onset comparison (PLAN.md section 9, 12; D46, D48, D94, D97).

Split from evaluate.py: segments_summary.csv rows of every method in a comparison group, latency over the attacks
every compared method detects, and cf_onset.csv. Reads results CSVs and scores, never the model.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from tsfm_ad import cache, data, score
from tsfm_ad.config import steps, with_variant

SEGMENTS = ("onset", "interior", "interior_eq", "offset")
FF_GROUPS = ("pre_active", "triggered_in_attack", "none")
RUN_COLS = ["run_key", "dataset", "model", "setup", "variant", "hash8"]
METHOD = [*RUN_COLS, "channel_set", "score", "agg", "N"]


def key_lits(d: dict) -> list[pl.Expr]:
    return [pl.lit(v).alias(k) for k, v in d.items()]


def run_rows(df: pl.DataFrame, keys: dict, front: list[str]) -> pl.DataFrame:
    """run_key first, then `front` columns, the rest, and the other run-key columns last."""
    df = df.with_columns(*key_lits(keys))
    rest = [c for c in df.columns if c not in RUN_COLS and c not in front]
    return df.select("run_key", *front, *rest, *RUN_COLS[1:])


def common_detected(table: pl.DataFrame, by) -> list[str]:
    """Attack ids that every method (`by`) in the table detects."""
    n_methods = table.select(list(by)).unique().height
    return (table.filter(pl.col("latency_s").is_not_null()).group_by("attack_id").agg(n=pl.len())
            .filter(pl.col("n") == n_methods)["attack_id"].to_list())


def latency_summary(table: pl.DataFrame, by=("run_key",), common=None) -> pl.DataFrame:
    """Per method (`by`): n_detected, median censored latency over all its attacks, and the median latency over the
    attacks every method in `table` detects (or over `common`, if given) (D48)."""
    by = list(by)
    common = common_detected(table, by) if common is None else common
    in_common = pl.col("attack_id").is_in(list(common)) & pl.col("latency_s").is_not_null()
    return table.group_by(by, maintain_order=True).agg(
        n_attacks=pl.len(), n_detected=pl.col("latency_s").is_not_null().sum(),
        latency_censored_median_s=pl.col("latency_censored_s").cast(pl.Float64).median(),
        latency_common_median_s=pl.col("latency_s").cast(pl.Float64).filter(in_common).median(),
        n_common=in_common.sum())


def _typed_attack_rows(df: pl.DataFrame) -> pl.DataFrame:
    """segments_per_attack rows read back as strings -> the numeric types the summary needs."""
    num = [c for c in df.columns if c.endswith(("_cov", "_chance")) or c.startswith(("latency", "cov_"))]
    det = [c for c in df.columns if c.endswith("_det")]
    return df.with_columns(*[pl.col(c).cast(pl.Float64) for c in num + ["p_normal"]],
                           *[pl.when(pl.col(c).is_null()).then(None).otherwise((pl.col(c) == "true").cast(pl.Float64))
                             .alias(c) for c in det])


def summarize(per_attack: pl.DataFrame) -> pl.DataFrame:
    """segments_summary rows of the methods in `per_attack`, which are compared with each other (one dataset,
    channel set, comparison score, agg and N): all attacks, per offset stratum, per FF group."""
    t = _typed_attack_rows(per_attack)
    common = common_detected(t, METHOD)   # over all compared methods, then restricted to each subset
    subsets = [("all", "all", pl.lit(True))]
    subsets += [(s, "all", pl.col("stratum") == s) for s in sorted(t["stratum"].drop_nulls().unique().to_list())]
    subsets += [("all", g, pl.col("ff_group") == g) for g in FF_GROUPS]
    out = []
    for stratum, group, cond in subsets:
        sub = t.filter(cond)
        if not sub.height:
            continue
        stats = sub.group_by(METHOD, maintain_order=True).agg(
            p_normal=pl.col("p_normal").first(),
            **{f"{s}_cov_mean": pl.col(f"{s}_cov").mean() for s in SEGMENTS},
            **{k: v for s in SEGMENTS for k, v in ((f"{s}_rate", pl.col(f"{s}_det").mean()),
                                                     (f"{s}_chance", pl.col(f"{s}_chance").mean()))},
            cov_post_origin_mean=pl.col("cov_post_origin").mean(), cov_pre_origin_mean=pl.col("cov_pre_origin").mean())
        lat = latency_summary(sub, METHOD, common=common)
        out.append(stats.join(lat, on=METHOD).with_columns(stratum=pl.lit(stratum), ff_group=pl.lit(group)))
    cols = ["run_key", "channel_set", "score", "agg", "N", "stratum", "ff_group", "n_attacks", "p_normal",
            *[f"{s}_cov_mean" for s in SEGMENTS], *[f"{s}_{x}" for s in SEGMENTS for x in ("rate", "chance")],
            "latency_common_median_s", "n_common", "latency_censored_median_s", "n_detected",
            "cov_post_origin_mean", "cov_pre_origin_mean", *RUN_COLS[1:]]
    return pl.concat(out).select(cols) if out else pl.DataFrame()


def update_summary(out: Path, groups: set) -> None:
    """Recompute segments_summary rows of every method in the comparison groups this run touched."""
    rows = pl.read_csv(out / "segments_per_attack.csv", infer_schema_length=0)
    cmp = pl.when(pl.col("score").is_in(["band", "dual"])).then(pl.lit("headline")).otherwise(pl.col("score"))
    rows = rows.with_columns(_cmp=cmp)
    parts = [summarize(g.drop("_cmp")) for k, g in rows.group_by(["dataset", "channel_set", "_cmp", "agg", "N"])
             if tuple(k) in groups]
    if parts:
        score.upsert_csv(out / "segments_summary.csv", pl.concat(parts, how="diagonal"),
                         ["run_key", "channel_set", "score", "agg", "N", "stratum", "ff_group"])


# ---- cf-onset comparison (D46, D97) ----

def cf_onset_table(j: pl.DataFrame, attacks: pl.DataFrame, N: int, col: str, thr: float) -> list[dict]:
    """Step-by-step comparison of the clean-context forecast (origin = onset s, h = t - s + 1) with the rolling
    forecast. `j` holds the cf steps (file, t, origin, h, `col`) joined with the rolling `origin_roll`, `col_roll`."""
    rows = []
    for aid, f, s, e in attacks.select("attack_id", "segment", "start_idx", "end_idx").iter_rows():
        g = j.filter((pl.col("file") == f) & (pl.col("origin") == s))
        t, hcf = g["t"].to_numpy(), g["h"].to_numpy()
        cf, roll = g[col].to_numpy(), g[f"{col}_roll"].to_numpy()
        post = g["origin_roll"].to_numpy() > s
        masks = {"onset": (t < s + N) & (t <= e), "interior": (t >= s + N) & (t <= e),
                 "interior_eq": (t >= s + N) & (t < s + 2 * N) & (e - s + 1 >= 2 * N), "offset": t > e}
        for name, m0 in masks.items():
            for side, m1 in (("pre", ~post), ("post", post)):
                m = m0 & m1
                if not m.any():
                    continue
                le = m & (hcf <= 30)
                rows.append({"attack_id": aid, "segment": name, "origin_side": side, "n_steps": int(m.sum()),
                             "n_hcf_le30": int(le.sum()), "score_rolling_mean": float(roll[m].mean()),
                             "score_cf_mean": float(cf[m].mean()),
                             "score_rolling_mean_hcf_le30": float(roll[le].mean()) if le.any() else None,
                             "score_cf_mean_hcf_le30": float(cf[le].mean()) if le.any() else None,
                             "cov_rolling": float((roll[m] > thr).mean()), "cov_cf": float((cf[m] > thr).mean())})
    return rows


def evaluate_cf(cfg, d, man, keys, out) -> None:
    """cf-onset: compare with the rolling run of the same model and setup, at the rolling run's thresholds."""
    roll_cfg = with_variant(cfg, "rolling")
    rd = cache.run_dir(roll_cfg)
    rman = score.read_manifest(roll_cfg, rd)
    N = steps(cfg, cfg["metrics"]["N_onset_s"])
    attack_tab = data.load_attacks(cfg)
    rows = []
    for name in [n for n in man["sets"] if n in rman["sets"]]:
        cf = pl.read_parquet(d / "scores" / name / "agg_test.parquet")
        roll = pl.read_parquet(rd / "scores" / name / "agg_test.parquet")
        thr = pl.read_parquet(rd / "scores" / name / "thresholds.parquet").filter(
            pl.col("calib_source") == rman["calib_sources"][0])
        for kd, ag in man["columns"]:
            col = f"{kd}_{ag}"
            j = cf.join(roll.select("file", "t", pl.col("origin").alias("origin_roll"), pl.col(col).alias(f"{col}_roll")),
                        on=["file", "t"], how="inner")
            t_val = thr.filter((pl.col("score") == kd) & (pl.col("agg") == ag))["threshold"].item()
            rows += [{"channel_set": name, "score": kd, "agg": ag, **r}
                     for r in cf_onset_table(j, attack_tab, N, col, t_val)]
    score.upsert_csv(out / "cf_onset.csv", run_rows(pl.DataFrame(rows), keys, ["channel_set", "score", "agg"]),
                     ["run_key", "channel_set", "score", "agg", "attack_id", "segment", "origin_side"])
