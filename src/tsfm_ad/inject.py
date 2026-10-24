"""Labelled anomaly injections into the LANL test days (PLAN.md 15.4, D143). Applied to raw per-minute values before
the log1p/z transform. A seed fixes the whole schedule; the manifest records every injection.

Types (brief): silence (the series drops to `magnitude` x normal), burst (failed auth + magnitude x the median of the
`baseline_min` raw minutes before the start), ramp (the series rises linearly to + magnitude x normal at the last
injected minute, then returns), shift (a persistent step of + magnitude x normal for the duration).
"""
from __future__ import annotations

import fnmatch

import numpy as np
import polars as pl

MANIFEST_SCHEMA = {"seed": pl.Int64, "inj_id": pl.String, "type": pl.String, "series": pl.String,
                   "group": pl.String, "magnitude": pl.Float64, "duration_min": pl.Int64, "replica": pl.Int64,
                   "start": pl.Int64, "end": pl.Int64}


def expand(patterns: list[str], names: list[str]) -> list[str]:
    out = [n for n in names if any(fnmatch.fnmatchcase(n, p) for p in patterns)]
    if not out:
        raise ValueError(f"targets {patterns} match no series")
    return out


def schedule(icfg: dict, seed: int, lo: int, hi: int, group_of: dict[str, str], replicas: int | None = None,
             avoid: list[tuple[int, int]] = ()) -> tuple[pl.DataFrame, list[str]]:
    """(manifest, dropped) for one seed: every (type, magnitude, duration) `replicas` times in minutes [lo, hi).
    No two injections of one group overlap, each blocked from gap_before_min before its start to gap_after_min after
    its end. `avoid` = minute ranges blocked for every group (the red-team windows, D147). Longest first, random target
    and start; an item that does not fit in 2,000 tries is dropped."""
    rng = np.random.default_rng(seed)
    names = list(group_of)
    reps = icfg["replicas"] if replicas is None else replicas
    items = [(t, float(m), int(d), r) for t, spec in icfg["types"].items() for m in spec["magnitudes"]
             for d in spec["durations"] for r in range(reps)]
    order = rng.permutation(len(items))
    items = sorted((items[i] for i in order), key=lambda x: -x[2])
    blocked: dict[str, list[tuple[int, int]]] = {g: list(avoid) for g in set(group_of.values())}
    rows, dropped = [], []
    gb, ga = icfg["gap_before_min"], icfg["gap_after_min"]
    for t, m, d, r in items:
        targets = expand(icfg["types"][t]["targets"], names)
        first = lo + (icfg["types"][t].get("baseline_min", 0))
        placed = False
        for _ in range(2000):
            s = str(rng.choice(targets))
            g = group_of[s]
            if hi - d <= first:
                break
            start = int(rng.integers(first, hi - d))
            a, b = start - gb, start + d + ga
            if all(b <= x or a >= y for x, y in blocked[g]):
                blocked[g].append((a, b))
                rows.append({"seed": seed, "inj_id": "", "type": t, "series": s, "group": g, "magnitude": m,
                             "duration_min": d, "replica": r, "start": start, "end": start + d})
                placed = True
                break
        if not placed:
            dropped.append(f"seed {seed}: {t} magnitude {m} duration {d} replica {r}")
    man = pl.DataFrame(rows, schema=MANIFEST_SCHEMA).sort("start")
    man = man.with_columns(inj_id=pl.format("s{}-{}", pl.col("seed"), pl.int_range(pl.len()).cast(pl.String)))
    return man, dropped


def apply(raw: dict[str, np.ndarray], man: pl.DataFrame, icfg: dict) -> tuple[dict[str, np.ndarray],
                                                                            dict[str, np.ndarray]]:
    """(injected raw values, labels) per series; inputs are not modified."""
    out = {k: v.astype(np.float64).copy() for k, v in raw.items()}
    lab = {k: np.zeros(len(v), np.int8) for k, v in raw.items()}
    for r in man.iter_rows(named=True):
        x, s, e, m = out[r["series"]], r["start"], r["end"], r["magnitude"]
        if lab[r["series"]][s:e].any():
            raise ValueError(f"injections overlap on {r['series']} at {s}")
        if r["type"] == "silence":
            x[s:e] = m * x[s:e]
        elif r["type"] == "burst":
            w = icfg["types"]["burst"]["baseline_min"]
            base = max(1.0, float(np.median(raw[r["series"]][max(0, s - w):s])))
            x[s:e] = x[s:e] + m * base
        elif r["type"] == "ramp":
            d = e - s
            x[s:e] = x[s:e] * (1.0 + m * np.arange(1, d + 1) / d)
        elif r["type"] == "shift":
            x[s:e] = x[s:e] * (1.0 + m)
        else:
            raise ValueError(f"unknown injection type {r['type']!r}")
        lab[r["series"]][s:e] = 1
    return out, lab
