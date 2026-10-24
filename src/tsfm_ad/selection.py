"""The selection rule D21 (PLAN.md section 8, D40, D41, D84, D85), applied to metrics.csv; picked on test results.

- base: "better of 1 and 2". Candidates `uni` and `mv-lit` rolling, both scored on the matched set mvlit34. If
  mv-lit wins, the base is mv-lit (scored on mvlit34), otherwise uni (scored on uni51).
- best: "best of 1-3". Candidates the base setup's rolling, ff-interp-block, frozen and dual, on the base setup's
  full channel set. Score band, `dual` for dual.
Metric: highest test PR-AUC with top-3 mean aggregation, ties by ROC-AUC; an exact tie keeps the candidate order.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "results" / "phase1" / "selection.csv"
NOTE = "picked on test results"
BASE_CANDIDATES = ("uni", "mv-lit")             # mv-acttgt and uni57 are never candidates (D40)
MATCHED_SET = "mvlit34"
FULL_SET = {"uni": "uni51", "mv-lit": "mvlit34"}
BEST_VARIANTS = {"rolling": "rolling", "ff-interp-block": "ff", "frozen": "frozen", "dual": "dual"}
KINDS = {**BEST_VARIANTS, "ff-interp-block-max60-testinf": "ff"}   # variant name -> kind
# reported in the same table, never candidates: (setup or None = the base, variant, channel set or None = full set)
BASE_REPORTED = [("uni", "rolling", "uni51"), ("mv-acttgt", "rolling", "mvacttgt41"), ("uni", "rolling", "mvacttgt41")]
BEST_REPORTED = [(None, "ff-interp-block-max60-testinf", None)]
SCHEMA = {"stage": pl.String, "decided_at": pl.String, "rule": pl.String, "candidate_run_key": pl.String,
          "channel_set": pl.String, "score": pl.String, "agg": pl.String, "pr_auc": pl.Float64,
          "roc_auc": pl.Float64, "rank": pl.Int64, "selected": pl.Boolean, "note": pl.String}
KEY_COLS = ("dataset", "model", "setup", "variant")


def rule_for(cfg: dict) -> dict:
    """cfg's selection rule restricted to cfg's dataset and model (size and device), so runs of other sizes or
    devices in the same metrics.csv never take part in the pick."""
    from tsfm_ad.config import model_tag

    return {**cfg.get("selection", {}), "dataset": cfg["dataset"]["key"], "model": model_tag(cfg)}


def parse_run_key(s: str) -> dict:
    """'dataset/model/setup/variant[@hash8]' -> dict with those keys (hash8 None when absent)."""
    parts = str(s).split("/")
    if len(parts) != 4:
        raise ValueError(f"run key {s!r} is not dataset/model/setup/variant[@hash8]")
    variant, _, h = parts[3].partition("@")
    return {"dataset": parts[0], "model": parts[1], "setup": parts[2], "variant": variant, "hash8": h or None}


def with_keys(df: pl.DataFrame) -> pl.DataFrame:
    """Make sure a results frame has run_key, dataset, model, setup, variant and hash8 (parsed from `run_key`
    when the separate columns are missing; run_key built from them when it is missing)."""
    if not all(c in df.columns for c in KEY_COLS):
        keys = pl.DataFrame([parse_run_key(s) for s in df["run_key"]],
                            schema={c: pl.String for c in (*KEY_COLS, "hash8")})
        if "hash8" in df.columns:
            keys = keys.with_columns(hash8=df["hash8"].cast(pl.String))
        df = pl.concat([df.drop([c for c in keys.columns if c in df.columns]), keys], how="horizontal")
    if "hash8" not in df.columns:
        df = df.with_columns(hash8=pl.lit(None, pl.String))
    if "run_key" not in df.columns:
        df = df.with_columns(run_key=pl.concat_str([pl.col(c) for c in KEY_COLS], separator="/"))
    return df


def _one(m: pl.DataFrame, setup: str, variant: str, channel_set: str, score: str) -> dict | None:
    rows = m.filter((pl.col("setup") == setup) & (pl.col("variant") == variant)
                    & (pl.col("channel_set") == channel_set) & (pl.col("score") == score)).unique(
        subset=["run_key", "hash8", "pr_auc", "roc_auc"], keep="first", maintain_order=True)
    if rows.height > 1:
        raise ValueError(f"{rows.height} metrics rows for {setup}/{variant} on {channel_set} ({score}): "
                         f"{list(zip(rows['run_key'], rows['hash8']))}; remove the stale rows from metrics.csv")
    return rows.row(0, named=True) if rows.height else None


def _pick_model(m: pl.DataFrame, rule: dict) -> tuple[str, str]:
    """The (dataset, model) whose uni and mv-lit rolling runs both have matched-set rows."""
    base = m.filter((pl.col("variant") == "rolling") & (pl.col("channel_set") == MATCHED_SET)
                    & (pl.col("score") == "band") & pl.col("setup").is_in(BASE_CANDIDATES))
    for key in ("dataset", "model"):
        if rule.get(key):
            base = base.filter(pl.col(key) == rule[key])
    pairs = (base.group_by("dataset", "model").agg(pl.col("setup").n_unique().alias("n"))
             .filter(pl.col("n") == len(BASE_CANDIDATES)).sort("dataset", "model"))
    if pairs.height > 1:   # several Timestral sizes have both; D16: the working model decides
        size = f"-{rule.get('model_size', '28M')}-"
        pairs = pairs.filter(pl.col("model").str.contains(size, literal=True))
    if pairs.height != 1:
        raise ValueError(f"need exactly one (dataset, model) with uni and mv-lit rolling on {MATCHED_SET}; "
                         f"found {pairs.select('dataset', 'model').rows()}. Run evaluate for both, or set "
                         "selection.dataset / selection.model")
    return pairs.select("dataset", "model").row(0)


def _key(c: dict) -> str:
    """run_key, with @hash8 appended when the metrics row has it separately."""
    return c["run_key"] if not c["hash8"] or "@" in c["run_key"] else f"{c['run_key']}@{c['hash8']}"


def _rows(stage, rule_txt, cands, reported, metric, tiebreak, agg) -> pl.DataFrame:
    now = datetime.now().isoformat(timespec="seconds")
    bad = [c["run_key"] for c in cands if c[metric] is None or c[metric] != c[metric]]
    if bad:
        raise ValueError(f"{metric} is undefined for {bad}")
    order = sorted(range(len(cands)), key=lambda i: (-cands[i][metric], -(cands[i][tiebreak] or 0.0), i))
    rank = {i: r + 1 for r, i in enumerate(order)}
    out = [{"stage": stage, "decided_at": now, "rule": rule_txt, "candidate_run_key": _key(c),
            "channel_set": c["channel_set"], "score": c["score"], "agg": agg, "pr_auc": c["pr_auc"],
            "roc_auc": c["roc_auc"], "rank": rank[i], "selected": rank[i] == 1, "note": NOTE}
           for i, c in enumerate(cands)]
    out += [{"stage": stage, "decided_at": now, "rule": rule_txt, "candidate_run_key": _key(c),
             "channel_set": c["channel_set"], "score": c["score"], "agg": agg, "pr_auc": c["pr_auc"],
             "roc_auc": c["roc_auc"], "rank": None, "selected": False,
             "note": f"reported only, not a candidate (D21, D40); {NOTE}"} for c in reported]
    return pl.DataFrame(out, schema=SCHEMA)


def tagged_checkpoint(tag: str) -> dict:
    """The `model.chronos2` block of the config in configs/ whose checkpoint carries `tag` (D136)."""
    from tsfm_ad.config import load_config

    for p in sorted((Path(__file__).resolve().parents[2] / "configs").glob("*.yaml")):
        block = load_config(p)["model"].get("chronos2", {})
        if block.get("tag") == tag:
            return copy.deepcopy(block)
    raise ValueError(f"no config in configs/ has a Chronos-2 checkpoint tagged {tag!r}")


def run_cfg(cfg: dict, key: str) -> dict:
    """A copy of cfg describing the TSFM run `dataset/model/setup/variant[@hash8]` of a results row: its model
    (chronos2-<rev7>-<device> or timestral-<size>-<rev7>-<device>), setup, variant kind and device; in-file warm-up;
    FF without exit (max 60 for -max60-testinf). Raises ValueError when cfg cannot describe that run (another
    dataset, resolution, revision or variant name, or not a TSFM run)."""
    from tsfm_ad.config import run_key

    k = parse_run_key(key)
    parts = k["model"].split("-")
    c = copy.deepcopy(cfg)
    if len(parts) == 3 and parts[0] == "chronos2":          # chronos2-<rev7>-<device>
        c["model"].update(name="chronos2", device=parts[2])
    elif len(parts) == 4 and parts[0] == "chronos2":        # chronos2-<tag>-<rev7>-<device> (D136: chronos-2-small)
        c["model"].update(name="chronos2", device=parts[3])
        c["model"]["chronos2"] = tagged_checkpoint(parts[1])
    elif len(parts) == 4 and parts[0] == "timestral":       # timestral-<size>-<rev7>-<device>
        c["model"].update(name="timestral", size=parts[1], device=parts[3])
    else:
        raise ValueError(f"{key} is not a Chronos-2 or Timestral run")
    c["setup"] = k["setup"]
    c["forecast"]["warmup"] = "in_file"
    name = re.sub(r"-c\d+$", "", k["variant"])     # 1 s variant names end in -c<cap>
    h = re.search(r"-h(\d+)$", name)               # D138: -h<H> for a horizon other than 30
    if h:
        c["forecast"]["H"], name = int(h.group(1)), name[:h.start()]
    c["variant"]["kind"] = KINDS.get(name, name)
    c["variant"]["ff"]["max_duration"] = 60 if name == "ff-interp-block-max60-testinf" else None
    want = "/".join(k[x] for x in KEY_COLS)
    if str(run_key(c)) != want:
        raise ValueError(f"config {cfg.get('_path')} cannot describe the run {want} (it gives {run_key(c)})")
    return c


def current_hash8(c: dict) -> str | None:
    """hash8 of run cfg c's cache directory, recomputed from config and code; None when that directory is missing."""
    from tsfm_ad import score

    try:
        d = score.source_dir(c)
    except FileNotFoundError:                       # no prepared data, or FF without its complete rolling calib
        return None
    return d.name.split("@")[-1] if d.exists() else None


def _stale(cfg: dict, row: dict) -> str | None:
    """None when a metrics row comes from its run's current forecast hash, else a description for the message."""
    cur = current_hash8(run_cfg(cfg, row["run_key"]))
    return None if cur == row["hash8"] else f"{_key(row)} (current: {f'@{cur}' if cur else 'no cache directory'})"


def check_pick(pick: dict, cfg: dict) -> None:
    """Raise LookupError when the run a pick was made on no longer has that forecast hash (D113)."""
    cur = current_hash8(run_cfg(cfg, pick["run_key"]))
    if cur != pick["hash8"]:
        raise LookupError(f"the {pick['stage']} pick {pick['run_key']} was made on forecasts that are not current "
                          f"({f'now @{cur}' if cur else 'no current cache directory'}): run its candidates and "
                          f"select --stage {pick['stage']} again")


def _decide(stage: str, metrics_csv: Path, rule: dict, cfg: dict | None) -> pl.DataFrame:
    metric, tiebreak, agg = rule.get("metric", "pr_auc"), rule.get("tiebreak", "roc_auc"), rule.get("agg", "topk")
    if not metrics_csv.exists():
        raise FileNotFoundError(f"{metrics_csv} is missing: run evaluate first")
    m = with_keys(pl.read_csv(metrics_csv, infer_schema_length=None, schema_overrides={"hash8": pl.String}))
    m = m.filter(pl.col("agg") == agg)
    if "calib_source" in m.columns:   # AUCs do not depend on it; keep one row per run
        m = m.filter(pl.col("calib_source") == "calib")
    if stage == "base":
        dataset, model = _pick_model(m, rule)
        m = m.filter((pl.col("dataset") == dataset) & (pl.col("model") == model))
        cands = [_one(m, s, "rolling", MATCHED_SET, "band") for s in BASE_CANDIDATES]
        reported = BASE_REPORTED
        rule_txt = (f"D21 base: uni vs mv-lit rolling on {MATCHED_SET}, highest test {metric} (band, {agg}), "
                    f"ties by {tiebreak}, exact ties keep uni")
        score_of = {}
    elif stage == "best":
        base = selected("base", metrics_csv.parent / "selection.csv")
        m = m.filter((pl.col("dataset") == base["dataset"]) & (pl.col("model") == base["model"]))
        full = FULL_SET[base["setup"]]
        score_of = {"dual": "dual"}
        cands = [_one(m, base["setup"], v, full, score_of.get(v, "band")) for v in BEST_VARIANTS]
        reported = [(s or base["setup"], v, cs or full) for s, v, cs in BEST_REPORTED]
        rule_txt = (f"D21 best: rolling, ff-interp-block, frozen, dual of base {base['setup']} on {full}, "
                    f"highest test {metric} ({agg}; band, dual score for dual), ties by {tiebreak}")
    else:
        raise ValueError(f"stage must be base or best, got {stage!r}")
    names = list(BASE_CANDIDATES) if stage == "base" else list(BEST_VARIANTS)
    missing = [n for n, c in zip(names, cands) if c is None]
    if missing:
        raise ValueError(f"select --stage {stage}: no {agg} metrics for candidates {missing} in {metrics_csv}")
    stale = [w for w in (_stale(cfg, c) for c in cands) if w] if cfg is not None else []
    if stale:
        raise ValueError(f"select --stage {stage}: the metrics.csv rows of {stale} are not from the current "
                         "forecasts: run their forecast, score and evaluate first")
    rep = []
    for s, v, cs in reported:
        r = _one(m, s, v, cs, score_of.get(v, "band"))
        if r is None:
            print(f"select: {s}/{v} on {cs} not in metrics.csv, not reported")
        elif cfg is not None and _stale(cfg, r):
            print(f"select: {s}/{v} on {cs} is not from the current forecasts, not reported")
        else:
            rep.append(r)
    return _rows(stage, rule_txt, cands, rep, metric, tiebreak, agg)


def select(stage: str, metrics_csv, rule: dict, cfg: dict | None = None) -> pl.DataFrame:
    """Apply D21 to metrics.csv and write this stage's rows to selection.csv next to it (other stages kept).

    With cfg (the CLI and pipeline pass it), every candidate's metrics rows must come from its current forecast hash
    (D113). A failed select removes this stage's rows from selection.csv, so an older pick is never used again.
    """
    metrics_csv = Path(metrics_csv)
    out_csv = metrics_csv.parent / "selection.csv"
    try:
        rows = _decide(stage, metrics_csv, rule, cfg)
    except Exception:
        _forget(out_csv, stage)
        raise
    if out_csv.exists():
        rows = pl.concat([pl.read_csv(out_csv, schema=SCHEMA).filter(pl.col("stage") != stage), rows])
    rows.write_csv(out_csv)
    mine = rows.filter(pl.col("stage") == stage)
    with pl.Config(fmt_str_lengths=90, tbl_width_chars=200, tbl_hide_dataframe_shape=True):
        print(mine.select("candidate_run_key", "channel_set", "score", "pr_auc", "roc_auc", "rank", "selected"))
    print(f"select {stage}: {mine.filter(pl.col('selected'))['candidate_run_key'][0]} ({NOTE}) -> {out_csv}")
    return mine


def _forget(out_csv: Path, stage: str) -> None:
    if out_csv.exists():
        rows = pl.read_csv(out_csv, schema=SCHEMA)
        if rows.filter(pl.col("stage") == stage).height:
            rows.filter(pl.col("stage") != stage).write_csv(out_csv)
            print(f"select {stage} failed: its previous pick was removed from {out_csv}")


def selected(stage: str, path=None) -> dict:
    """The pick of a stage from selection.csv (default results/phase1/selection.csv): setup, variant, kind,
    channel_set (the setup's full set), score, dataset, model, run_key, pr_auc, roc_auc."""
    path = Path(path) if path else DEFAULT_CSV
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run `tsfm-ad select --stage {stage}` first")
    df = pl.read_csv(path, schema=SCHEMA).filter((pl.col("stage") == stage) & pl.col("selected"))
    if df.height != 1:
        raise LookupError(f"{path} has {df.height} selected rows for stage {stage}: run select --stage {stage}")
    row = df.row(0, named=True)
    k = parse_run_key(row["candidate_run_key"])
    if stage == "best":
        base = selected("base", path)
        if (k["setup"], k["model"]) != (base["setup"], base["model"]):
            raise LookupError(f"the best pick {row['candidate_run_key']} is not on the current base "
                              f"{base['setup']} ({base['model']}): run select --stage best again")
    return {"stage": stage, "setup": k["setup"], "variant": k["variant"],
            "kind": BEST_VARIANTS.get(k["variant"], k["variant"]), "channel_set": FULL_SET[k["setup"]],
            "score": row["score"], "dataset": k["dataset"], "model": k["model"], "hash8": k["hash8"],
            "run_key": row["candidate_run_key"], "pr_auc": row["pr_auc"], "roc_auc": row["roc_auc"]}
