"""`smoke` and `all` (PLAN.md sections 8, 11 and 14): forecast -> score -> evaluate chains in the planned order.

Both run the model of configs/base.yaml (Chronos-2, D117). The Timestral configs in configs/timestral/ are never
loaded here (Timestral is paused, CLAUDE.md), so neither command can touch a Timestral model.

A run that fails is logged and the next run goes on; the command exits non-zero at the end if any run failed.
Resumable: cached forecast files are skipped (cache.py), and score + evaluate are skipped when their inputs, score,
metric and channel settings and code are unchanged (`scores/done.json`). No config file is ever edited:
`setup: selected` and `variant.kind: selected` are resolved in memory from selection.csv (D41).
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

import polars as pl

from tsfm_ad import (baselines, cache, compare, d128, data, diagnostics, evaluate, forecast, latency, mps_check, plots,
                     score, selection)
from tsfm_ad.config import SRC_DIR, load_config, model_id, resolve_selected, run_key, with_variant

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
SCORE_SOURCES = ("score.py", "evaluate.py", "summary.py", "tapr_wrap.py", "ff_results.py", "data.py")
SMOKE_SETUPS = ("uni", "uni57", "mv-lit", "mv-acttgt")
FAIL_SCHEMA = {"run": pl.String, "error": pl.String, "at": pl.String}


def mps_csv() -> Path:
    """results/phase1/mps_check.csv: the check decides the device of the real runs, so it is not a smoke output."""
    return Path(load_config(CONFIGS / "base.yaml")["paths"]["results"]) / "mps_check.csv"


class Runner:
    """Runs steps in order; a failing step is printed with its traceback, logged and skipped."""

    def __init__(self, name: str, device: str | None = None):
        self.name, self.device = name, device
        self.failures: list[dict] = []
        self.runs: list[dict] = []           # resolved TSFM run configs, for latency.csv
        self.log = Path(load_config(CONFIGS / "base.yaml")["paths"]["cache"]) / "logs" / f"{name}_failures.csv"
        self._write_log()

    def load(self, name: str) -> dict:
        cfg = load_config(CONFIGS / name)
        if self.device:
            cfg["model"]["device"] = self.device
        return cfg

    def step(self, label: str, fn, *args) -> bool:
        print(f"\n=== [{self.name}] {label}", flush=True)
        t0 = time.time()
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 - one failed run must not stop the others
            traceback.print_exc()
            self.failures.append({"run": label, "error": f"{type(e).__name__}: {e}",
                                  "at": datetime.now().isoformat(timespec="seconds")})
            self._write_log()
            print(f"=== FAILED [{self.name}] {label}: {type(e).__name__}: {e}", flush=True)
            return False
        print(f"=== ok [{self.name}] {label} ({time.time() - t0:.1f} s)", flush=True)
        return True

    def chain(self, label: str, cfg: dict) -> bool:
        return self.step(label, run_chain, cfg, self.runs)

    def _write_log(self) -> None:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(self.failures, schema=FAIL_SCHEMA).write_csv(self.log)

    def finish(self) -> int:
        self._write_log()
        if not self.failures:
            print(f"\n{self.name}: every step passed")
            return 0
        print(f"\n{self.name}: {len(self.failures)} step(s) FAILED (list in {self.log}):")
        for f in self.failures:
            print(f"  - {f['run']}: {f['error']}")
        return 1


# ---- one run ----

def _inputs(cfg: dict) -> list[str]:
    """The cache files score + evaluate read (path, size, mtime), scores excluded."""
    kind = cfg["variant"]["kind"]
    dirs = {"dual": [cache.run_dir(cfg, "rolling"), cache.run_dir(cfg, "frozen")],
            "cf-onset": [cache.run_dir(cfg), cache.run_dir(cfg, "rolling")]}.get(kind, [score.source_dir(cfg)])
    out = []
    for d in dirs:
        for p in sorted(d.rglob("*.parquet")):
            if "scores" not in p.relative_to(d).parts:
                st = p.stat()
                out.append(f"{p}:{st.st_size}:{st.st_mtime_ns}")
    return out


def _fingerprint(cfg: dict) -> str:
    """Everything score + evaluate depend on beyond the forecast hash; `channels` defines the scored sets (D112)."""
    code = {n: hashlib.sha256((SRC_DIR / n).read_bytes()).hexdigest() for n in SCORE_SOURCES}
    blob = {"score": cfg["score"], "metrics": cfg["metrics"], "channels": cfg["channels"],
            "results": cfg["paths"]["results"], "code": code, "inputs": _inputs(cfg)}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def _has_rows(cfg: dict, d: Path) -> bool:
    path = Path(cfg["paths"]["results"]) / ("cf_onset.csv" if cfg["variant"]["kind"] == "cf-onset" else "metrics.csv")
    if not path.exists():
        return False
    df = pl.read_csv(path, infer_schema_length=0, columns=["run_key", "hash8"])
    return df.filter((pl.col("run_key") == str(run_key(cfg))) & (pl.col("hash8") == d.name.split("@")[-1])).height > 0


def score_and_evaluate(cfg: dict) -> None:
    """score then evaluate, unless both already ran on exactly these inputs, settings and code."""
    d = score.source_dir(cfg)
    fp, done = _fingerprint(cfg), d / "scores" / "done.json"
    if done.exists() and json.loads(done.read_text()).get("fingerprint") == fp and _has_rows(cfg, d):
        print(f"score + evaluate {run_key(cfg)}@{d.name.split('@')[-1]}: up to date, skipped")
        return
    score.run_score(cfg)
    evaluate.run_evaluate(cfg)
    done.write_text(json.dumps({"fingerprint": fp, "at": datetime.now().isoformat(timespec="seconds")}))


def run_chain(cfg: dict, runs: list | None = None) -> None:
    """One run: the forecasts its kind needs first, then its own forecast, score and evaluate."""
    cfg = resolve_selected(cfg)
    kind = cfg["variant"]["kind"]
    mps_check.guard(cfg, mps_csv())
    if kind == "ff":
        forecast.run_forecast(with_variant(cfg, "rolling"), "calib")     # FF thresholds come from it (D24)
    if kind == "dual":
        forecast.run_forecast(with_variant(cfg, "rolling"))
        forecast.run_forecast(with_variant(cfg, "frozen"))
    forecast.run_forecast(cfg)
    score_and_evaluate(cfg)
    if runs is not None:
        runs.append(cfg)


def run_baselines_chain(r: Runner, cfg: dict, label: str) -> None:
    if r.step(f"{label}: baselines forecast", baselines.run_baselines, cfg, "all"):
        for b in baselines.BASELINES:
            r.step(f"{label}: baseline {b} score + evaluate", score_and_evaluate, baselines.baseline_cfg(cfg, b))


def run_d128(cfg: dict) -> None:
    """The D128 effect of one run (PLAN.md 14.5), skipped when d128_effect.csv already has it for this hash."""
    cfg = resolve_selected(cfg)
    mps_check.guard(cfg, mps_csv())
    d128.run_d128(cfg, "all", skip_done=True)


def d128_steps(r: Runner, label: str, items: list[tuple[str, dict]]) -> None:
    for name, c in items:
        r.step(f"{label}: D128 effect, {name}", run_d128, c)


def select_stage(cfg: dict, stage: str) -> None:
    selection.select(stage, Path(cfg["paths"]["results"]) / "metrics.csv", selection.rule_for(cfg), cfg)


def selected_cfg(cfg: dict) -> dict:
    """cfg with the best (setup, variant) of selection.csv."""
    c = copy.deepcopy(cfg)
    c.update(setup="selected", selection_stage="best")
    c["variant"]["kind"] = "selected"
    return c


def write_tables(results: str, entries: list[tuple[dict, bool]], runs: list[dict]) -> None:
    """latency.csv and quantile_diagnostics.csv (D133) over the TSFM runs of this results directory and
    size_latency.csv over `entries`."""
    mine = [c for c in runs if c["paths"]["results"] == results]
    latency.write_latency(mine, Path(results))
    diagnostics.write_diagnostics(mine, Path(results))
    latency.write_size_latency(entries, Path(results))


# ---- smoke ----

def smoke_variants(cfg: dict, setup: str) -> list[tuple[str, dict]]:
    """Every variant of PLAN.md 8 "smoke 10 s" for one setup, rolling first (FF, dual and cf-onset need it)."""
    c = copy.deepcopy(cfg)
    c["setup"] = setup
    pre = copy.deepcopy(c)
    pre["forecast"]["warmup"] = "prepend"
    ff60 = copy.deepcopy(with_variant(c, "ff"))
    ff60["variant"]["ff"]["max_duration"] = 60
    return [("rolling", c), ("prepend", pre), ("frozen", with_variant(c, "frozen")), ("dual", with_variant(c, "dual")),
            ("ff-interp-block", with_variant(c, "ff")), ("ff-interp-block-max60-testinf", ff60),
            ("cf-onset", with_variant(c, "cf-onset"))]


def smoke(r: Runner) -> None:
    """The whole chain on both smoke slices (results in results/smoke), then the MPS check of D54."""
    s10, s1 = r.load("smoke.yaml"), r.load("smoke_1s.yaml")
    for c in (s10, s1):
        r.step(f"prepare {c['dataset']['key']}", data.prepare, c)
    for setup in SMOKE_SETUPS:
        for label, c in smoke_variants(s10, setup):
            r.chain(f"smoke 10 s: {setup} {label}", c)
    run_baselines_chain(r, s10, "smoke 10 s")
    uni, mv = ({**copy.deepcopy(s10), "setup": k} for k in ("uni", "mv-lit"))
    d128_steps(r, "smoke 10 s", [("uni rolling", uni), ("mv-lit rolling", mv),
                                 ("mv-lit cf-onset", with_variant(mv, "cf-onset")),
                                 ("mv-lit frozen", with_variant(mv, "frozen"))])
    for stage in ("base", "best"):
        r.step(f"smoke 10 s: select --stage {stage} (exercise only, never used)", select_stage, s10, stage)
    best = selected_cfg(s10)
    r.chain("smoke 10 s: the selected best (exercises setup/kind: selected)", best)
    for label, c in (("rolling", s1), ("ff-interp-block", with_variant(s1, "ff")),
                     ("cf-onset", with_variant(s1, "cf-onset"))):
        r.chain(f"smoke 1 s: uni {label}", c)
    run_baselines_chain(r, s1, "smoke 1 s")
    r.step("smoke: latency tables", write_tables, s10["paths"]["results"], [(best, True), (s10, False)], r.runs)
    r.step("smoke 10 s: plot", plots.run_plots, s10)
    r.step("smoke 1 s: plot", plots.run_plots, s1, "uni")
    for c in (s10, s1):
        for item in c["mps_check"]:
            for setup in item["setups"]:
                size = item.get("size")            # a Timestral size; Chronos-2 items have none
                r.step(f"MPS check (D54) {c['dataset']['key']} {model_id(c) if size is None else size} {setup}",
                       mps_check.check_and_write, c, size, setup, mps_csv())


# ---- all ----

# PLAN.md 14.8: inference estimate from the latency measured on HAI (smoke calls_*.csv), per device; the range is
# best = uni + FF vs mv-lit + FF. The smoke (about 33 min on cpu) and scoring come on top.
ESTIMATE = ("PLAN.md 14.8: the default matrix (10 s) is about {default} of inference on {device}; --optional 10s "
            "adds prepend and FF max30/120, about {opt10} more; --optional (all) adds the 1 s block on top, about "
            "{opt1} more (D124, D131). Each forecast prints its own measured estimate before it starts.")
ESTIMATE_H = {"cpu": ("8.4-8.7 h", "4.6-5.1 h", "47.5-48.8 h"), "mps": ("4.8-4.9 h", "2.6-2.9 h", "26.4-27.2 h")}


def run_all(r: Runner, optional: str | None = None) -> None:
    """The Chronos-2 Phase 1 matrix in the order of PLAN.md sections 8 and 14. `optional`: None, "10s" (prepend
    and FF max30/120 after the matrix) or "all" (those, then the 1 s block, D131). Experiment 4 (model sizes) is
    deferred until Timestral permission (D123): Chronos-2 has one size with the 21 cache quantile levels."""
    base, r1 = r.load("base.yaml"), r.load("res1s_uni.yaml")
    default, opt10, opt1 = ESTIMATE_H.get(base["model"]["device"], ("?", "?", "?"))
    print(ESTIMATE.format(default=default, device=base["model"]["device"], opt10=opt10, opt1=opt1), flush=True)
    smoke(r)
    for c in (base, r1):
        r.step(f"prepare {c['dataset']['key']}", data.prepare, c)
    exp1, exp2 = r.load("exp1_uni.yaml"), r.load("exp2_mv.yaml")
    r.chain("exp 1: uni rolling (+ calib2)", exp1)
    r.chain("exp 1: uni cf-onset", with_variant(exp1, "cf-onset"))
    r.chain("exp 1: uni57 rolling", r.load("exp1_uni57.yaml"))
    r.chain("exp 2: mv-lit rolling (+ calib2)", exp2)
    r.chain("exp 2: mv-lit cf-onset", with_variant(exp2, "cf-onset"))
    acttgt = r.load("exp2_mv_acttgt.yaml")
    r.chain("exp 2: mv-acttgt rolling", acttgt)
    d128_steps(r, "exp 1-2", [("uni rolling", exp1), ("uni cf-onset", with_variant(exp1, "cf-onset")),
                              ("mv-lit rolling", exp2), ("mv-lit cf-onset", with_variant(exp2, "cf-onset")),
                              ("mv-acttgt rolling", acttgt)])
    run_baselines_chain(r, r.load("exp5_baselines.yaml"), "exp 5")
    r.step("select --stage base (D21, picked on test results)", select_stage, exp1, "base")
    for name, label in (("exp3b_frozen.yaml", "exp 3b: frozen"), ("exp3c_dual.yaml", "exp 3c: dual"),
                        ("exp3a_ff_interp_block.yaml", "exp 3a: ff-interp-block"),
                        ("exp3a_ff_interp_block_max60.yaml", "exp 3a: ff-interp-block-max60-testinf")):
        r.chain(label, r.load(name))
    d128_steps(r, "exp 3b", [("frozen on the base", r.load("exp3b_frozen.yaml"))])
    r.step("select --stage best (D21, picked on test results)", select_stage, exp1, "best")
    print("\nexp 4 (model sizes): deferred until Timestral permission (D123); not run", flush=True)
    entries = [(selected_cfg(base), True), (exp1, False)]
    if optional:
        run_optional_10s(r)
    r.step("latency.csv and size_latency.csv", write_tables, base["paths"]["results"], entries, r.runs)
    r.step("plot 10 s", plots.run_plots, base)
    r.step("compare: matched false alarms and paired bootstrap (D135)", compare.run_compare, base)
    if optional == "all":
        run_optional_1s(r)
        r.step("latency.csv and size_latency.csv (with the 1 s runs)", write_tables, base["paths"]["results"],
               entries, r.runs)
        r.step("plot 1 s", plots.run_plots, r1, "uni")


def run_optional_10s(r: Runner) -> None:
    """The 10 s runs behind --optional (PLAN.md 14.7, D124): the prepend warm-up and the FF max-duration
    sensitivity. They run before the 1 s block so their tables and plots exist while it runs (D131)."""
    r.chain("optional: prepend warm-up", r.load("opt_prepend.yaml"))
    sens = r.load("opt_ff_max_sens.yaml")
    for k in sens["sweep"]["max_duration"]:
        c = copy.deepcopy(sens)
        c["variant"]["ff"]["max_duration"] = k
        r.chain(f"optional: ff-interp-block-max{k}", c)


def run_optional_1s(r: Runner) -> None:
    """The 1 s comparison block behind --optional (all) with its 10 s FF reference (D52, D124)."""
    r1 = r.load("res1s_uni.yaml")
    r.chain("optional, 1 s: uni rolling", r1)
    run_baselines_chain(r, r1, "optional, 1 s")
    r.chain("optional, 1 s: uni cf-onset", with_variant(r1, "cf-onset"))
    r.chain("optional, 10 s reference for 1 s (D52): uni ff-interp-block", r.load("res10s_uni_ff.yaml"))
    r.chain("optional, 1 s: uni ff-interp-block", r.load("res1s_ff_interp_block.yaml"))
