"""LANL cyber1 to per-minute series (PLAN.md 15.1-15.3, D140-D142). Streams the gzip files with DuckDB, never loads a
file whole.

Writes cache/lanl/prepared/: `dst_minute.parquet` and `src_minute.parquet` (auth events per minute and destination
or source computer), `tenant.parquet` (auth_total, auth_failed, users_distinct per minute), `src_bytes_minute.parquet`
(flow bytes per minute and source computer; not used for a series, D148: flows thin out after day 14) and
`raw.parquet` (minute + the 13 series, raw values). results/phase2/series.csv names
every series and how it was selected; splits.csv the day ranges.
"""
from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import polars as pl

AUTH_COLS = {"time": "BIGINT", "src_user": "VARCHAR", "dst_user": "VARCHAR", "src_comp": "VARCHAR",
             "dst_comp": "VARCHAR", "auth_type": "VARCHAR", "logon_type": "VARCHAR", "orient": "VARCHAR",
             "result": "VARCHAR"}
FLOW_COLS = {"time": "BIGINT", "duration": "BIGINT", "src_comp": "VARCHAR", "src_port": "VARCHAR",
             "dst_comp": "VARCHAR", "dst_port": "VARCHAR", "protocol": "VARCHAR", "packets": "BIGINT",
             "bytes": "BIGINT"}


def _csv(path: Path, cols: dict, limit_lines: int | None = None) -> str:
    spec = "{" + ", ".join(f"'{k}': '{v}'" for k, v in cols.items()) + "}"
    src = (f"read_csv('{path}', header=false, columns={spec}, delim=',', quote='', escape='', "
           f"compression='gzip', nullstr='?')")
    return f"(SELECT * FROM {src} LIMIT {limit_lines})" if limit_lines else src


def _run(sql: str, tmp: str) -> float:
    import duckdb

    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{tmp}'; SET memory_limit='12GB'; SET preserve_insertion_order=false;")
    con.execute(sql)
    con.close()
    return time.time() - t0


def aggregate(cfg: dict, limit_lines: int | None = None, only: tuple[str, ...] = ("tenant", "dst", "src")) -> None:
    """The three DuckDB scans, in parallel processes (each gzip file is decompressed on one thread)."""
    src, out = Path(cfg["paths"]["lanl"]), Path(cfg["paths"]["cache"]) / "prepared"
    out.mkdir(parents=True, exist_ok=True)
    tmp = str(out / "duckdb_tmp")
    auth, flows = _csv(src / "auth.txt.gz", AUTH_COLS, limit_lines), _csv(src / "flows.txt.gz", FLOW_COLS, limit_lines)
    jobs = {
        "tenant": f"""COPY (SELECT (time - 1) // 60 AS minute, count(*) AS auth_total,
                      count(*) FILTER (WHERE result = 'Fail') AS auth_failed,
                      count(DISTINCT src_user) FILTER (WHERE src_user NOT LIKE '%$@%') AS users_distinct
                      FROM {auth} GROUP BY minute) TO '{out / "tenant.parquet"}' (FORMAT parquet)""",
        "dst": f"""COPY (SELECT (time - 1) // 60 AS minute, dst_comp, count(*) AS n FROM {auth}
                   WHERE dst_comp IS NOT NULL GROUP BY minute, dst_comp) TO '{out / "dst_minute.parquet"}'
                   (FORMAT parquet)""",
        "src": f"""COPY (SELECT (time - 1) // 60 AS minute, src_comp, count(*) AS n FROM {auth}
                   WHERE src_comp IS NOT NULL GROUP BY minute, src_comp) TO '{out / "src_minute.parquet"}'
                   (FORMAT parquet)""",
        "flows": f"""COPY (SELECT (time - 1) // 60 AS minute, src_comp, sum(bytes) AS bytes FROM {flows}
                     WHERE src_comp IS NOT NULL AND bytes IS NOT NULL GROUP BY minute, src_comp)
                     TO '{out / "src_bytes_minute.parquet"}' (FORMAT parquet)""",
    }
    with ProcessPoolExecutor(max_workers=3) as ex:
        futs = {k: ex.submit(_run, sql, f"{tmp}_{k}") for k, sql in jobs.items() if k in only}
        for k, f in futs.items():
            print(f"lanl: {k} scan done in {f.result():.0f} s", flush=True)


def fit_minutes(cfg: dict) -> tuple[int, int]:
    a, b = cfg["data"]["fit_days"]
    return a * 1440, (b + 1) * 1440


def top_n(df: pl.DataFrame, key: str, val: str, cfg: dict, exclude=()) -> pl.DataFrame:
    """The top-N `key` values by total `val` over the fit minutes only (no test data in the selection), leaving out
    `exclude` (the hosts already chosen as DC-like, so the two groups are different machines, D148)."""
    lo, hi = fit_minutes(cfg)
    return (df.filter((pl.col("minute") >= lo) & (pl.col("minute") < hi) & ~pl.col(key).is_in(list(exclude)))
            .group_by(key)
            .agg(pl.col(val).sum().alias("fit_total")).sort(["fit_total", key], descending=[True, False])
            .head(cfg["data"]["top_n"]).with_row_index("rank", offset=1))


def build_flows_raw(cfg: dict) -> pl.DataFrame:
    """The flows sub-study (D149): minute + bytes out of the top-N flow sources on the fit days (`fhost_*`)."""
    src = Path(cfg["data"]["prepared_dir"])
    p = Path(cfg["paths"]["cache"]) / "prepared"
    p.mkdir(parents=True, exist_ok=True)
    n = cfg["data"]["minutes"]
    raw = pl.DataFrame({"minute": np.arange(n, dtype=np.int64)})
    df = pl.read_parquet(src / "src_bytes_minute.parquet").filter(pl.col("minute") < n)
    rows = []
    for r in top_n(df, "src_comp", "bytes", cfg).iter_rows(named=True):
        s = f"fhost_{r['rank']}"
        raw = raw.join(df.filter(pl.col("src_comp") == r["src_comp"]).select("minute", pl.col("bytes").alias(s)),
                       on="minute", how="left")
        rows.append({"series": s, "group": s, "source": "flows", "entity": r["src_comp"], "rank": r["rank"],
                     "fit_total": r["fit_total"], "definition": f"flow bytes with source {r['src_comp']}, at the "
                     "flow's start minute"})
    raw = raw.fill_null(0).with_columns(pl.exclude("minute").cast(pl.Float64))
    _write_tables(cfg, rows)
    raw.write_parquet(p / "raw.parquet")
    return raw


def _write_tables(cfg: dict, rows: list[dict]) -> None:
    out = Path(cfg["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_csv(out / "series.csv")
    d = cfg["data"]
    pl.DataFrame([{"split": k, "first_day": d[f"{k}_days"][0], "last_day": d[f"{k}_days"][1],
                   "first_minute": d[f"{k}_days"][0] * 1440, "end_minute": (d[f"{k}_days"][1] + 1) * 1440}
                  for k in ("fit", "calib", "test")]).write_csv(out / "splits.csv")


def build_raw(cfg: dict) -> pl.DataFrame:
    """minute + the 13 raw series (0 where a minute has no event), and results/phase2/series.csv."""
    if cfg["data"].get("source") == "flows":
        return build_flows_raw(cfg)
    p = Path(cfg["paths"]["cache"]) / "prepared"
    n = cfg["data"]["minutes"]
    raw = pl.DataFrame({"minute": np.arange(n, dtype=np.int64)})
    tenant = pl.read_parquet(p / "tenant.parquet")
    raw = raw.join(tenant, on="minute", how="left")
    rows = [{"series": s, "group": "tenant", "source": "auth", "entity": "", "rank": None, "fit_total": None,
             "definition": d} for s, d in (("auth_total", "auth events"), ("auth_failed", "auth events with Fail"),
                                           ("users_distinct", "distinct source users, machine accounts excluded"))]
    for name, file, key, val, prefix, source in (("dc", "dst_minute.parquet", "dst_comp", "n", "dc", "auth"),
                                                  ("host", "src_minute.parquet", "src_comp", "n", "host", "auth")):
        df = pl.read_parquet(p / file)
        top = top_n(df, key, val, cfg, exclude=[r["entity"] for r in rows if r["group"] == "dc"])
        for r in top.iter_rows(named=True):
            s = f"{prefix}_{r['rank']}"
            one = df.filter(pl.col(key) == r[key]).select("minute", pl.col(val).alias(s))
            raw = raw.join(one, on="minute", how="left")
            rows.append({"series": s, "group": name, "source": source, "entity": r[key], "rank": r["rank"],
                         "fit_total": r["fit_total"], "definition": (f"auth events with destination {r[key]}"
                         if name == "dc" else f"auth events with source computer {r[key]}")})
    raw = raw.fill_null(0).with_columns(pl.exclude("minute").cast(pl.Float64))
    raw = raw.filter(pl.col("minute") < n)
    _write_tables(cfg, rows)
    raw.write_parquet(p / "raw.parquet")
    return raw


def series_names(cfg: dict) -> list[str]:
    return [s for g in cfg["data"]["groups"].values() for s in g]


def fit_stats(raw: pl.DataFrame, cfg: dict) -> dict[str, tuple[float, float]]:
    """Mean and std of log1p(raw) per series over the fit minutes only (D141)."""
    lo, hi = fit_minutes(cfg)
    f = raw.filter((pl.col("minute") >= lo) & (pl.col("minute") < hi))
    out = {}
    for s in series_names(cfg):
        v = np.log1p(f[s].to_numpy())
        sd = float(v.std())
        out[s] = (float(v.mean()), sd if sd > 1e-9 else 1.0)   # a constant fit series: rounding leaves ~1e-16
    return out


def transform(raw_values: np.ndarray, stats: list[tuple[float, float]]) -> np.ndarray:
    """(V, T) raw -> (V, T) z of log1p, with the fit stats of each row."""
    mu = np.array([m for m, _ in stats])[:, None]
    sd = np.array([s for _, s in stats])[:, None]
    return (np.log1p(np.maximum(raw_values, 0.0)) - mu) / sd
