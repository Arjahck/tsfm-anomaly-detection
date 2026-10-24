"""Forecast Fallback results (PLAN.md 8 exp 3a, 12; D44, D77): episodes, activity and per-attack attribution.

Reads the per-file `<split>/<file>.ff_episodes.csv` that the FF forecast writes next to its cache. Not a forecast
source (unlike context.py), so editing this file never changes a forecast hash.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from tsfm_ad import data
from tsfm_ad.config import steps
from tsfm_ad.context import EPISODE_SCHEMA


def episode_files(run_dir: Path) -> list[Path]:
    return sorted(Path(run_dir).glob("*/*.ff_episodes.csv"))


def read_episodes(run_dir: Path) -> pl.DataFrame:
    """All `<split>/<file>.ff_episodes.csv` of an FF run directory, with a `split` column."""
    parts = [pl.read_csv(p, schema_overrides=EPISODE_SCHEMA).with_columns(split=pl.lit(p.parent.name))
             for p in episode_files(run_dir)]
    empty = pl.DataFrame(schema={**EPISODE_SCHEMA, "split": pl.String})
    return pl.concat([empty, *parts], how="vertical_relaxed")


def ff_attack_state(episodes: pl.DataFrame, attacks: pl.DataFrame, N: int,
                    channels: list[str] | None = None) -> pl.DataFrame:
    """FF attribution per attack (D44), from `episodes_frame` rows of the test files.

    onset s = start_idx. Active at onset: an episode with start_t <= s <= end_t. Age at onset: s - the oldest such
    start_t. First trigger after onset: the earliest start_t in [s, end_idx + N], minus s. Group: `pre_active` if
    active at onset, else `triggered_in_attack` if such a trigger exists, else `none`. `channels` restricts the
    episodes to a scored channel set.
    """
    if channels is not None:
        episodes = episodes.filter(pl.col("channel").is_in(channels))
    rows = []
    for a in attacks.iter_rows(named=True):
        s, stop = a["start_idx"], a["end_idx"] + N
        ep = episodes.filter(pl.col("file") == a["segment"])
        act = ep.filter((pl.col("start_t") <= s) & (pl.col("end_t") >= s))
        trig = ep.filter((pl.col("start_t") >= s) & (pl.col("start_t") <= stop))
        active = act.height > 0
        first = int(trig["start_t"].min()) - s if trig.height else None
        rows.append({
            "attack_id": a["attack_id"],
            "ff_group": "pre_active" if active else ("triggered_in_attack" if first is not None else "none"),
            "ff_active_at_onset": active,
            "ff_n_channels_active_at_onset": act["channel"].n_unique() if active else 0,
            "ff_fallback_age_at_onset_steps": s - int(act["start_t"].min()) if active else None,
            "ff_first_trigger_after_onset_steps": first,
        })
    return pl.DataFrame(rows, schema={"attack_id": pl.String, "ff_group": pl.String, "ff_active_at_onset": pl.Boolean,
                                      "ff_n_channels_active_at_onset": pl.Int64,
                                      "ff_fallback_age_at_onset_steps": pl.Int64,
                                      "ff_first_trigger_after_onset_steps": pl.Int64})


def activity(cfg: dict, run_dir: Path, channels: list[str]) -> pl.DataFrame:
    """One row per (split, file, channel): n_triggers, fallback_steps (substituted steps) and their share of the
    file's scored steps. Channels that never triggered get zeros."""
    W, ep = steps(cfg, cfg["forecast"]["W_s"]), read_episodes(run_dir)
    files = [(p.parent.name, p.name.removesuffix(".ff_episodes.csv")) for p in episode_files(run_dir)]
    scored = {f: len(data.load_segment(cfg, f)) - W for _, f in files}
    grid = pl.DataFrame([{"split": s, "file": f, "channel": c, "scored_steps": scored[f]}
                         for s, f in files for c in channels],
                        schema={"split": pl.String, "file": pl.String, "channel": pl.String, "scored_steps": pl.Int64})
    per = ep.group_by("split", "file", "channel").agg(n_triggers=pl.len(), fallback_steps=pl.col("n_steps").sum())
    return (grid.join(per, on=["split", "file", "channel"], how="left")
            .with_columns(pl.col("n_triggers").fill_null(0).cast(pl.Int64),
                          pl.col("fallback_steps").fill_null(0).cast(pl.Int64))
            .with_columns(fallback_frac=pl.col("fallback_steps") / pl.col("scored_steps")))


def _replace_run(path: Path, df: pl.DataFrame, rk: str) -> None:
    """Drop every row of run key `rk` from a results CSV, then append df (which may be empty)."""
    new = df.select(pl.all().cast(pl.String))
    if path.exists():
        new = pl.concat([pl.read_csv(path, infer_schema_length=0).filter(pl.col("run_key") != rk), new],
                        how="diagonal")
    path.parent.mkdir(parents=True, exist_ok=True)
    new.sort("run_key", maintain_order=True).write_csv(path)


def write_ff_results(cfg: dict, run_dir: Path, keys: dict, tau: dict[str, float], channels: list[str]) -> None:
    """ff_thresholds.csv, ff_episodes.csv and ff_activity.csv (PLAN.md 12) for one FF run. Rows of the same
    run_key are replaced (any older hash too, D91); other runs' rows are kept. `keys` = score.key_columns."""
    res = Path(cfg["paths"]["results"])

    def keyed(df):
        return df.select(pl.lit(keys["run_key"]).alias("run_key"), pl.all(),
                         *[pl.lit(v).alias(k) for k, v in keys.items() if k != "run_key"])

    thr = pl.DataFrame({"channel": list(tau), "tau": list(tau.values())}, schema={"channel": pl.String,
                                                                                    "tau": pl.Float64})
    _replace_run(res / "ff_thresholds.csv", keyed(thr), keys["run_key"])
    ep = read_episodes(run_dir)
    attacks = data.load_attacks(cfg)
    overlaps, onsets = [], []
    for r in ep.iter_rows(named=True):
        a = attacks.filter(pl.col("segment") == r["file"])
        overlaps.append(";".join(a.filter((pl.col("start_idx") <= r["end_t"])
                                          & (pl.col("end_idx") >= r["start_t"]))["attack_id"]))
        onsets.append(";".join(a.filter(pl.col("start_idx").is_between(r["start_t"], r["end_t"]))["attack_id"]))
    ep = ep.select("split", "file", "channel", "start_t", "end_t", "n_steps", "exit",
                   pl.Series("overlaps_attack_id", overlaps, dtype=pl.String),
                   pl.Series("active_at_onset_of", onsets, dtype=pl.String))
    _replace_run(res / "ff_episodes.csv", keyed(ep), keys["run_key"])
    _replace_run(res / "ff_activity.csv", keyed(activity(cfg, run_dir, channels)), keys["run_key"])
