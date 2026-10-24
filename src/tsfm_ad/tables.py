"""Attack table and the prepare CSVs: results/<phase>/channels.csv, attacks.csv, splits.csv (PLAN.md 3, 5, 12)."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import polars as pl

from tsfm_ad.data import LABELS, TIME_FMT, _ts, attack_events, channel_sets, slice_rows

SPLIT_ROLES = {
    "fit": "normalization statistics, baseline error quantiles",
    "ref": "frozen context, seasonal-refday reference day, prepend warm-up source",
    "calib": "detection thresholds, FF per-feature thresholds",
    "calib2": "sensitivity thresholds only (overlaps fit)",
    "test": "evaluation only",
    "excluded": "identical to test3's first 12 h; used nowhere",
}


def _stratum(df: pl.DataFrame, s: int, e: int, strata: list[dict]) -> str:
    for st in strata:
        if (df[st["tag"]][s:e + 1] != st["normal"]).any():
            return st["name"]
    return "other"


def test_events(cfg: dict, raw: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """All attack events of the full test files at 1 s, joined with the PDF table by (file, event) (D56, D47)."""
    rows = []
    for f in cfg["dataset"]["test_files"]:
        df = raw[f]
        proc = df.select(LABELS[1:]).to_numpy()
        for r in attack_events(df["attack"], df["time"], f).iter_rows(named=True):
            s, e = r["start_idx"], r["end_idx"]
            r["processes"] = "+".join(p for i, p in enumerate(("P1", "P2", "P3")) if proc[s:e + 1, i].any())
            r["stratum"] = _stratum(df, s, e, cfg["channels"]["strata"])
            rows.append(r)
    ev = pl.DataFrame(rows).with_columns(pl.col("event").cast(pl.Int64))
    pdf = pl.read_csv(cfg["paths"]["attacks_pdf"], schema_overrides={"pdf_page": pl.String})
    out = ev.join(pdf, on=["file", "event"], how="left")
    if out["pdf_id"].null_count() or out.height != pdf.height:
        raise ValueError(f"label events ({ev.height}) and PDF table ({pdf.height}) do not match one to one")
    return out.rename({"pdf_id": "attack_id", "scenarios": "pdf_scenarios", "targets": "pdf_targets",
                       "n_steps": "duration_s"})


def attacks_at_resolution(cfg: dict, events: pl.DataFrame, test_segs, z: dict) -> pl.DataFrame:
    """Attacks inside the test segments, with step indices at the run's resolution (inclusive end)."""
    res = cfg["dataset"]["resolution_s"]
    rows = []
    for seg in test_segs:
        t = z[seg.name]["time"]
        t0, t1 = t[0], t[-1] + timedelta(seconds=res - 1)
        for r in events.filter(pl.col("file") == seg.file).iter_rows(named=True):
            if r["end"] < t0 or r["start"] > t1:
                continue
            if r["start"] < t0 or r["end"] > t1:
                raise ValueError(f"{r['attack_id']} is cut by the bounds of segment {seg.name}")
            s1 = int((r["start"] - t0).total_seconds())
            e1 = int((r["end"] - t0).total_seconds())
            rows.append({"attack_id": r["attack_id"], "segment": seg.name, "file": seg.file, "event": r["event"],
                         "start_idx": s1 // res, "end_idx": e1 // res, "n_steps": e1 // res - s1 // res + 1,
                         "start_idx_1s": s1, "end_idx_1s": e1, "start": r["start"], "end": r["end"],
                         "duration_s": r["duration_s"], "stratum": r["stratum"], "processes": r["processes"]})
        # the binned labels of the segment must give exactly these events
        ev = attack_events(z[seg.name]["attack"], t, seg.name)
        mine = [(a["start_idx"], a["end_idx"]) for a in rows if a["segment"] == seg.name]
        if list(zip(ev["start_idx"], ev["end_idx"])) != mine:
            raise ValueError(f"binned labels of {seg.name} disagree with the 1 s attack events")
    schema = {"attack_id": pl.String, "segment": pl.String, "file": pl.String, "event": pl.Int64,
              "start_idx": pl.Int32, "end_idx": pl.Int32, "n_steps": pl.Int32, "start_idx_1s": pl.Int32,
              "end_idx_1s": pl.Int32, "start": pl.Datetime("us"), "end": pl.Datetime("us"),
              "duration_s": pl.Int32, "stratum": pl.String, "processes": pl.String}
    return pl.DataFrame(rows, schema=schema)


def window_stats(s: int, e: int, W: int, H: int) -> tuple[int | None, int | None]:
    """Rolling windows (origins W + kH) covering steps s..e: count, and steps whose origin is after onset s."""
    if s < W:
        return None, None
    o_s = W + ((s - W) // H) * H
    o_e = W + ((e - W) // H) * H
    return (o_e - o_s) // H + 1, max(0, e - (o_s + H) + 1)


def attacks_csv(cfg: dict, b: dict) -> pl.DataFrame:
    """One row per test attack; the 10 s and 1 s columns do not depend on the run's resolution."""
    H, W_s, N_s = cfg["forecast"]["H"], cfg["forecast"]["W_s"], cfg["metrics"]["N_onset_s"]
    ev = b["events"].select("attack_id", "pdf_scenarios", "pdf_targets", "pdf_page")
    rows = []
    for a in b["attacks"].join(ev, on="attack_id").iter_rows(named=True):
        s1, e1 = a["start_idx_1s"], a["end_idx_1s"]
        s10, e10 = s1 // 10, e1 // 10
        n10, post10 = window_stats(s10, e10, W_s // 10, H)
        n1, post1 = window_stats(s1, e1, W_s, H)
        L10, N10 = e10 - s10 + 1, N_s // 10
        rows.append({
            "attack_id": a["attack_id"], "file": a["file"], "event": a["event"],
            "start": a["start"].strftime(TIME_FMT), "end": a["end"].strftime(TIME_FMT),
            "duration_s": a["duration_s"], "steps_10s": L10, "processes": a["processes"],
            "pdf_scenarios": a["pdf_scenarios"], "pdf_targets": a["pdf_targets"], "pdf_page": a["pdf_page"],
            "stratum": a["stratum"], "history_steps": s10,
            "n_windows_10s": n10, "post_onset_steps_10s": post10, "n_windows_1s": n1, "post_onset_steps_1s": post1,
            "interior_empty_10s": L10 <= N10, "interior_eq_10s": L10 >= 2 * N10,
            "in_timeline": a["attack_id"] in cfg["plots"]["timeline_attacks"]})
    return pl.DataFrame(rows)


def channels_csv(cfg: dict, b: dict) -> pl.DataFrame:
    res = cfg["dataset"]["resolution_s"]
    fit_raw = [slice_rows(b["raw"][s.file], s.start, s.end) for s in b["segments"]["fit"]]
    fit_raw = pl.concat([d.select(b["roles"]["channel"].to_list()) for d in fit_raw])
    stats = dict(zip(b["stats"]["channel"], zip(b["stats"]["mean"], b["stats"]["std"])))
    test = pl.concat([b["raw"][f] for f in cfg["dataset"]["test_files"]])
    sets = {k: v for k, v in channel_sets(cfg, b["roles"]).items() if "-" not in k}
    for name, members in sets.items():
        digits = "".join(ch for ch in name if ch.isdigit())
        if digits and int(digits) != len(members):
            raise ValueError(f"channel set {name} has {len(members)} channels")
    rows = []
    for r in b["roles"].iter_rows(named=True):
        c = r["channel"]
        mean, std = stats.get(c, (fit_raw[c].mean(), fit_raw[c].std()))
        rows.append({"channel": c, "resolution_s": res, "process": r["process"], "role": r["role"],
                     "rule": r["rule"], "n_unique_train": r["n_unique_train"],
                     "change_rate_train": r["change_rate_train"], "mean_fit": mean, "std_fit": std,
                     "varies_in_test": test[c].n_unique() > 1, **{k: c in v for k, v in sets.items()}})
    return pl.DataFrame(rows)


def splits_csv(cfg: dict, b: dict) -> pl.DataFrame:
    res = cfg["dataset"]["resolution_s"]
    W = cfg["forecast"]["W_s"] // res
    specs = [(s.name, split, s.file, s.start, s.end) for split, v in b["segments"].items() for s in v]
    specs += [(e["name"], "excluded", e["file"], _ts(e.get("start")), _ts(e.get("end")))
              for e in cfg["dataset"].get("excluded", [])]
    rows = []
    for name, split, file, start, end in specs:
        t = slice_rows(b["raw"][file], start, end)["time"]
        n = t.len()
        scored = n // res - W if split in ("calib", "calib2", "test") else 0
        rows.append({"segment": name, "split": split, "role": SPLIT_ROLES[split], "source_file": file,
                     "start": t[0].strftime(TIME_FMT), "end": t[-1].strftime(TIME_FMT), "rows_1s": n,
                     "steps_10s": n // 10, "scored_steps": scored, "resolution_s": res})
    return pl.DataFrame(rows)


def _merge_by_resolution(path: Path, df: pl.DataFrame) -> pl.DataFrame:
    """Replace this resolution's rows in an existing CSV and keep the others."""
    if path.exists():
        old = pl.read_csv(path, schema=df.schema)
        df = pl.concat([old.filter(pl.col("resolution_s") != df["resolution_s"][0]), df])
    return df.sort("resolution_s", descending=True, maintain_order=True)


def write_results(cfg: dict, b: dict) -> None:
    out = Path(cfg["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    attacks_csv(cfg, b).write_csv(out / "attacks.csv")
    for name, df in (("channels.csv", channels_csv(cfg, b)), ("splits.csv", splits_csv(cfg, b))):
        _merge_by_resolution(out / name, df).write_csv(out / name)
    print(f"wrote {out}/attacks.csv, channels.csv, splits.csv")


def summary(b: dict) -> dict:
    """Counts to check against PLAN.md sections 3-5."""
    roles = b["roles"]["role"].value_counts().sort("role")
    att = b["attacks"]
    return {"roles": dict(zip(roles["role"], roles["count"])), "attacks": att.height,
            "attack_steps": int(att["n_steps"].sum()),
            "steps": {k: v.height for k, v in b["z"].items()},
            "label_steps_test": int(np.sum([b["z"][s.name]["attack"].sum() for s in b["segments"]["test"]]))}
