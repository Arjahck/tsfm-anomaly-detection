"""HAI 21.03: reading, channel roles, downsampling, normalization, segments, attack events (PLAN.md 3-5)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

LABELS = ["attack", "attack_P1", "attack_P2", "attack_P3"]
SPLITS = ("fit", "ref", "calib", "calib2", "test")
ROLES = ("dropped", "step", "actuator", "continuous")
TIME_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Segment:
    """A segment spec: rows [start, end] (1 s rows, inclusive) of a raw file; None = file start / end."""
    name: str
    split: str
    file: str
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class SegmentData:
    """One prepared segment at the run's resolution. Z holds every non-dropped channel in z units."""
    name: str                 # e.g. "test1", "train1a", "reference"
    split: str                # fit | ref | calib | calib2 | test
    file: str                 # raw HAI file it was cut from
    time: np.ndarray          # (L,) datetime64[us], bin start
    labels: np.ndarray        # (L,) int8, binned `attack` (ground truth)
    labels_proc: np.ndarray   # (3, L) int8, binned attack_P1, attack_P2, attack_P3 (diagnostics only)
    Z: np.ndarray             # (C, L) float32, z-scored with fit statistics
    channels: list[str]       # C channel names, the row order of Z

    def __len__(self) -> int:
        return self.Z.shape[1]

    def rows(self, names: list[str]) -> np.ndarray:
        """(len(names), L) float32 copy of the named channels, in the given order."""
        idx = [self.channels.index(n) for n in names]
        return self.Z[idx]


@dataclass(frozen=True)
class Group:
    """One forecast call group of a setup: targets are forecast (jointly if multivariate), covariates past-only."""
    name: str
    targets: list[str]
    covariates: list[str]


def tag_columns(df: pl.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in ("time", "file", *LABELS)]


def _ts(s) -> datetime | None:
    return None if s is None else datetime.strptime(str(s), TIME_FMT)


def read_hai_file(path) -> pl.DataFrame:
    """Read one HAI csv(.gz): time as Datetime, every tag Float64, labels Int8 (D4); last row dropped (D3)."""
    df = pl.read_csv(path, infer_schema_length=0)
    df = df.select(
        pl.col("time").str.strptime(pl.Datetime("us"), TIME_FMT, strict=True),
        *[pl.col(c).cast(pl.Float64, strict=True) for c in tag_columns(df)],
        *[pl.col(c).cast(pl.Int8, strict=True) for c in LABELS],
    )
    return df.head(df.height - 1)


def slice_rows(df: pl.DataFrame, start=None, end=None) -> pl.DataFrame:
    if start is not None:
        df = df.filter(pl.col("time") >= start)
    if end is not None:
        df = df.filter(pl.col("time") <= end)
    return df


def channel_roles(train_df: pl.DataFrame, rules: dict) -> pl.DataFrame:
    """Roles by the rule of PLAN.md 3.4, on 1 s rows. A `file` column, if present, keeps changes within files."""
    files = train_df["file"].to_numpy() if "file" in train_df.columns else None
    same = np.ones(train_df.height - 1, bool) if files is None else files[1:] == files[:-1]
    out = []
    for c in tag_columns(train_df):
        x = train_df[c].to_numpy()
        n_unique = int(train_df[c].n_unique())
        rate = float(np.mean((x[1:] != x[:-1])[same]))
        if n_unique == 1:
            role, rule = "dropped", "constant on fit+calib rows"
        elif rate < rules["step_max_change_rate"]:
            role, rule = "step", f"change rate < {rules['step_max_change_rate']:.0%}"
        elif c.endswith("D") and c in rules["actuator_commands"]:
            role, rule = "actuator", "PDF valve/pump command"
        else:
            role, rule = "continuous", "default"
        out.append({"channel": c, "process": c.split("_")[0], "role": role, "rule": rule,
                    "n_unique_train": n_unique, "change_rate_train": rate})
    return pl.DataFrame(out)


def downsample(df: pl.DataFrame, roles: pl.DataFrame, resolution_s: int) -> pl.DataFrame:
    """Drop the dropped tags; bin = floor(time, res): mean for continuous/actuator, last for step, max for labels."""
    role = dict(zip(roles["channel"], roles["role"]))
    keep = [c for c in tag_columns(df) if role[c] != "dropped"]
    labels = [c for c in LABELS if c in df.columns]
    if not df["time"].is_sorted():
        raise ValueError("rows must be sorted by time")
    if resolution_s == 1:
        return df.select("time", *keep, *labels)
    aggs = [pl.col(c).last() if role[c] == "step" else pl.col(c).mean() for c in keep]
    out = (df.with_columns(pl.col("time").dt.truncate(f"{resolution_s}s"))
           .group_by("time", maintain_order=True)
           .agg(pl.len().alias("_n"), *aggs, *[pl.col(c).max() for c in labels]))
    if (out["_n"] != resolution_s).any():
        raise ValueError(f"partial {resolution_s} s bin: segment bounds must be aligned to the resolution")
    return out.select("time", *keep, *labels).sort("time")


def fit_norm(dfs: list[pl.DataFrame], channels: list[str]) -> pl.DataFrame:
    """Per-channel mean and std (ddof=1) over the concatenated frames (the fit set, D7)."""
    x = pl.concat([d.select(channels) for d in dfs])
    stats = pl.DataFrame({"channel": channels,
                          "mean": [x[c].mean() for c in channels],
                          "std": [x[c].std() for c in channels]})
    bad = stats.filter(~(pl.col("std") > 0))["channel"].to_list()
    if bad:
        raise ValueError(f"zero or undefined fit std for {bad}")
    return stats


def apply_norm(df: pl.DataFrame, stats: pl.DataFrame) -> pl.DataFrame:
    """z = (x - mean) / std as Float32 for the channels in stats; time and labels pass through."""
    z = [((pl.col(c) - m) / s).cast(pl.Float32).alias(c) for c, m, s in stats.iter_rows()]
    return df.select("time", *z, *[c for c in LABELS if c in df.columns])


def make_segments(cfg: dict) -> dict[str, list[Segment]]:
    """Segment specs per split from `dataset.splits` (PLAN.md section 5)."""
    out = {}
    for split in SPLITS:
        out[split] = [Segment(s["name"], split, s["file"], _ts(s.get("start")), _ts(s.get("end")))
                      for s in cfg["dataset"]["splits"].get(split) or []]
    names = [s.name for segs in out.values() for s in segs]
    if len(names) != len(set(names)):
        raise ValueError(f"segment names must be unique across splits: {names}")
    return out


def attack_events(labels, time, file: str) -> pl.DataFrame:
    """Runs of label 1: event (1-based, in order), start_idx/end_idx (inclusive), start/end times, n_steps."""
    y = np.asarray(labels).astype(np.int8)
    t = np.asarray(time)
    d = np.diff(np.concatenate([[0], y, [0]]))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    return pl.DataFrame({
        "file": [file] * len(starts),
        "event": np.arange(1, len(starts) + 1, dtype=np.int32),
        "start_idx": starts.astype(np.int32), "end_idx": ends.astype(np.int32),
        "start": t[starts], "end": t[ends],
        "n_steps": (ends - starts + 1).astype(np.int32),
    }, schema_overrides={"start": pl.Datetime("us"), "end": pl.Datetime("us")})


# ---- prepared data on disk: cache/<dataset>/prepared/ ----

def prepared_dir(cfg: dict) -> Path:
    return Path(cfg["paths"]["cache"]) / cfg["dataset"]["key"] / "prepared"


def _manifest(cfg: dict) -> dict:
    path = prepared_dir(cfg) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run `tsfm-ad prepare --config {cfg.get('_path')}` first")
    return json.loads(path.read_text())


def load_segment(cfg: dict, name: str) -> SegmentData:
    info = _manifest(cfg)["segments"][name]
    df = pl.read_parquet(prepared_dir(cfg) / f"{name}.parquet")
    channels = info["channels"]
    return SegmentData(
        name=name, split=info["split"], file=info["file"],
        time=df["time"].to_numpy(),
        labels=df["attack"].to_numpy().astype(np.int8),
        labels_proc=df.select(LABELS[1:]).to_numpy().T.astype(np.int8).copy(),
        Z=np.ascontiguousarray(df.select(channels).to_numpy().T, dtype=np.float32),
        channels=channels)


def load_split(cfg: dict, split: str) -> list[SegmentData]:
    return [load_segment(cfg, s.name) for s in make_segments(cfg)[split]]


def load_roles(cfg: dict) -> pl.DataFrame:
    return pl.read_parquet(prepared_dir(cfg) / "roles.parquet")


def load_norm_stats(cfg: dict) -> pl.DataFrame:
    return pl.read_parquet(prepared_dir(cfg) / "norm_stats.parquet")


def load_attacks(cfg: dict) -> pl.DataFrame:
    """Test attacks at the run's resolution: attack_id, segment, start_idx, end_idx (inclusive), n_steps, stratum..."""
    return pl.read_parquet(prepared_dir(cfg) / "attacks.parquet")


def setup_groups(cfg: dict, setup: str, roles: pl.DataFrame | None = None) -> list[Group]:
    """Forecast groups of a setup. univariate: one group `all`; multivariate: one group per process."""
    roles = load_roles(cfg) if roles is None else roles
    spec = cfg["channels"]["setups"][setup]

    def pick(procs, kinds):
        return [c for c, p, r in roles.select("channel", "process", "role").iter_rows() if p in procs and r in kinds]

    if spec["mode"] == "univariate":
        return [Group("all", pick(spec["processes"], spec["targets"]), [])]
    return [Group(p, pick([p], spec["targets"]), pick([p], spec["covariates"])) for p in spec["processes"]]


def channel_sets(cfg: dict, roles: pl.DataFrame | None = None) -> dict[str, list[str]]:
    """Scored channel sets: each setup's targets (uni51, uni57, mvlit34, mvacttgt41) and their `-<extra>` views."""
    roles = load_roles(cfg) if roles is None else roles
    out = {}
    for setup, spec in cfg["channels"]["setups"].items():
        out[spec["channel_set"]] = [c for g in setup_groups(cfg, setup, roles) for c in g.targets]
    for suffix, drop in cfg["channels"].get("extra_sets", {}).items():
        for name in list(out):
            out[f"{name}-{suffix}"] = [c for c in out[name] if c not in drop]
    return out


def array_digest(df: pl.DataFrame) -> str:
    """sha256 of a prepared frame's column names and values (independent of parquet metadata)."""
    h = hashlib.sha256(json.dumps(df.columns).encode())
    for c in df.columns:
        h.update(np.ascontiguousarray(df[c].to_numpy()).tobytes() if df[c].dtype != pl.String
                 else "\n".join(df[c].to_list()).encode())
    return h.hexdigest()


def roles_rows(cfg: dict, raw: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """The 1 s rows roles are computed on (fit + calib rows, D57), with a `file` column."""
    parts = [slice_rows(raw[r["file"]], _ts(r.get("start")), _ts(r.get("end"))).with_columns(file=pl.lit(r["file"]))
             for r in cfg["channels"]["rules"]["roles_rows"]]
    return pl.concat(parts)


def segment_frame(raw: pl.DataFrame, seg: Segment, roles: pl.DataFrame, res: int) -> pl.DataFrame:
    df = slice_rows(raw, seg.start, seg.end)
    if df.height == 0:
        raise ValueError(f"segment {seg.name} is empty")
    def sec_of_day(t):
        return t.hour * 3600 + t.minute * 60 + t.second

    end_next = df["time"][-1] + timedelta(seconds=1)
    if sec_of_day(df["time"][0]) % res or sec_of_day(end_next) % res:
        raise ValueError(f"segment {seg.name} is not aligned to {res} s")
    return downsample(df, roles, res)


def build(cfg: dict, raw: dict[str, pl.DataFrame] | None = None) -> dict:
    """Everything `prepare` writes, in memory: raw, roles, stats, segments (z frames), events (1 s), attacks."""
    from tsfm_ad import tables

    res = cfg["dataset"]["resolution_s"]
    segs = make_segments(cfg)
    files = {s.file for v in segs.values() for s in v} | set(cfg["dataset"]["test_files"])
    files |= {r["file"] for r in cfg["channels"]["rules"]["roles_rows"]}
    if raw is None:
        raw = {f: read_hai_file(Path(cfg["paths"]["data"]) / f"{f}.csv.gz") for f in sorted(files)}
    roles = channel_roles(roles_rows(cfg, raw), cfg["channels"]["rules"])
    expected = cfg["channels"]["rules"].get("expected_counts")
    counts = {r: roles.filter(pl.col("role") == r).height for r in ROLES}
    if expected and counts != expected:
        raise ValueError(f"channel role counts {counts} differ from expected {expected}")
    kept = roles.filter(pl.col("role") != "dropped")["channel"].to_list()
    frames = {s.name: segment_frame(raw[s.file], s, roles, res) for v in segs.values() for s in v}
    stats = fit_norm([frames[s.name] for s in segs["fit"]], kept)
    z = {name: apply_norm(df, stats) for name, df in frames.items()}
    events = tables.test_events(cfg, raw)
    attacks = tables.attacks_at_resolution(cfg, events, segs["test"], z)
    return {"raw": raw, "roles": roles, "stats": stats, "segments": segs, "z": z, "events": events,
            "attacks": attacks}


def prepare(cfg: dict) -> None:
    """Write cache/<dataset>/prepared/*.parquet + manifest.json, and channels.csv, attacks.csv, splits.csv."""
    from tsfm_ad import tables

    b = build(cfg)
    out = prepared_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"dataset": cfg["dataset"]["key"], "resolution_s": cfg["dataset"]["resolution_s"], "segments": {}}
    for split, segs in b["segments"].items():
        for s in segs:
            df = b["z"][s.name]
            df.write_parquet(out / f"{s.name}.parquet")
            manifest["segments"][s.name] = {
                "split": split, "file": s.file, "start": str(df["time"][0]), "end": str(df["time"][-1]),
                "n_steps": df.height, "channels": tag_columns(df), "sha256": array_digest(df)}
    for name in ("roles", "stats", "attacks"):
        fname = "norm_stats" if name == "stats" else name
        b[name].write_parquet(out / f"{fname}.parquet")
        manifest[f"{fname}_sha256"] = array_digest(b[name].select(pl.all().cast(pl.String)))
    parts = [v["sha256"] for _, v in sorted(manifest["segments"].items())]
    parts += [manifest[k] for k in ("roles_sha256", "norm_stats_sha256", "attacks_sha256")]
    manifest["digest"] = hashlib.sha256("".join(parts).encode()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    tables.write_results(cfg, b)
    print(f"prepared {cfg['dataset']['key']}: {len(manifest['segments'])} segments in {out}; "
          f"digest {manifest['digest'][:8]}")
