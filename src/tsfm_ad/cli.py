"""Single entry point: `uv run tsfm-ad <cmd> --config configs/X.yaml [--split ...] [--device ...]` (PLAN.md 11).

Modules other than data are imported inside each command, so the CLI works before they exist.
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

from tsfm_ad.config import load_config, resolve_selected, set_seeds

SPLIT_CHOICES = ["calib", "calib2", "test", "ref", "all"]
NEEDS_RUN = ("forecast", "baselines", "score", "evaluate", "plot", "d128", "diagnostics")


def _module(name: str):
    try:
        return importlib.import_module(f"tsfm_ad.{name}")
    except ModuleNotFoundError as e:
        if e.name == f"tsfm_ad.{name}":
            sys.exit(f"tsfm_ad.{name} is not implemented yet")
        raise


def cmd_prepare(cfg, args):
    _module("data").prepare(cfg)


def cmd_forecast(cfg, args):
    _module("forecast").run_forecast(cfg, args.split)


def cmd_baselines(cfg, args):
    _module("baselines").run_baselines(cfg, args.split)


def cmd_score(cfg, args):
    _module("score").run_score(cfg)


def cmd_evaluate(cfg, args):
    _module("evaluate").run_evaluate(cfg)


def cmd_select(cfg, args):
    selection = _module("selection")
    metrics_csv = Path(cfg["paths"]["results"]) / "metrics.csv"
    selection.select(args.stage, metrics_csv, selection.rule_for(cfg), cfg)


def cmd_d128(cfg, args):
    _module("d128").run_d128(cfg, args.split)


def cmd_diagnostics(cfg, args):
    _module("diagnostics").write_diagnostics([cfg], Path(cfg["paths"]["results"]))


def cmd_compare(cfg, args):
    _module("compare").run_compare(cfg)


def cmd_p2(cfg, args):
    """Phase 2 (PLAN.md 15): prepare | forecast | evaluate | redteam | plot | mps-check | all; --smoke for the slice."""
    p2, ev = _module("p2"), _module("p2_eval")
    c = p2.load_cfg(args.config, smoke=args.smoke)
    flows = c["data"].get("source") == "flows"      # the flows sub-study reads the main study's scans (D149)
    if args.stage in ("prepare", "all") and not args.smoke:
        lanl = _module("lanl")
        if not flows:
            lanl.aggregate(c)
        lanl.build_raw(c)
    if args.stage == "mps-check" or (args.stage == "all" and args.smoke):
        ev.mps_check(c)
    if args.stage in ("forecast", "all"):
        p2.forecast(c, runs=args.runs.split(",") if args.runs else None)
    if args.stage in ("evaluate", "all"):
        ev.evaluate(c)
    if args.stage in ("redteam", "all") and not args.smoke and not flows:
        ev.redteam(c)
    if args.stage in ("plot", "all"):
        _module("p2_plots").run_plots(c)


def cmd_paper(cfg, args):
    _module("paper").run_paper(cfg)


def cmd_plot(cfg, args):
    _module("plots").run_plots(cfg)


def cmd_restart_plot(cfg, args):
    _module("restart_plot").run(args.config)


def cmd_smoke(cfg, args):
    pipeline = _module("pipeline")
    r = pipeline.Runner("smoke", args.device)
    pipeline.smoke(r)
    return r.finish()


def cmd_all(cfg, args):
    pipeline = _module("pipeline")
    r = pipeline.Runner("all", args.device)
    pipeline.run_all(r, optional=args.optional)
    return r.finish()


COMMANDS = {
    "prepare": (cmd_prepare, "read, drop, downsample, normalize, segments; channel, attack and split CSVs"),
    "forecast": (cmd_forecast, "rolling / FF / frozen / prepend / cf-onset inference into the cache"),
    "baselines": (cmd_baselines, "baseline quantiles into the cache"),
    "score": (cmd_score, "channel scores, aggregation, thresholds (cache only)"),
    "evaluate": (cmd_evaluate, "AUCs, TaPR, point metrics, segments (cache only)"),
    "select": (cmd_select, "--stage base|best: apply D21 to metrics.csv, write selection.csv"),
    "plot": (cmd_plot, "figures (cache and results only)"),
    "restart-plot": (cmd_restart_plot, "restart_timeline.png: A402 forecast every 5 min and every minute (D154)"),
    "p2": (cmd_p2, "Phase 2 LANL: --stage prepare|forecast|evaluate|redteam|plot|mps-check|all [--smoke]"),
    "compare": (cmd_compare, "matched false-alarm comparison and paired bootstrap intervals (D135; scores only)"),
    "paper": (cmd_paper, "the paper's tables and figures (results and the Phase 2 cache only), then paper/paper.pdf"),
    "d128": (cmd_d128,"size of the D128 constant-row guard: adapter vs raw Chronos-2 on the calls it changes"),
    "diagnostics": (cmd_diagnostics, "quantile crossings, D128 constant rows and band widths per split (cache only)"),
    "smoke": (cmd_smoke, "the whole chain on both smoke slices plus the MPS check (ignores --config)"),
    "all": (cmd_all, "smoke, then the Phase 1 matrix of PLAN.md sections 8 and 14 (ignores --config)"),
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tsfm-ad", description="TSFM anomaly detection demo (Chronos-2; Timestral paused)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, (_, help_text) in COMMANDS.items():
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--config", default="configs/base.yaml")
        s.add_argument("--split", choices=SPLIT_CHOICES, default="all")
        s.add_argument("--device", choices=["cpu", "mps"], default=None, help="overrides model.device")
        if name == "select":
            s.add_argument("--stage", choices=["base", "best"], required=True)
        if name == "p2":
            s.add_argument("--stage", choices=["prepare", "forecast", "evaluate", "redteam", "plot", "mps-check",
                                               "all"], default="all")
            s.add_argument("--smoke", action="store_true", help="the smoke slice (PLAN.md 15.7)")
            s.add_argument("--runs", default=None, help="comma list of forecast runs (default: all of the config)")
        if name == "all":
            s.add_argument("--optional", nargs="?", const="all", choices=["10s", "all"], default=None,
                           help="also the optional runs (PLAN.md 14.7): `10s` = prepend and FF max30/120; "
                                "`all` (the default of a bare --optional) = those, then the 1 s block")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.device:
        cfg["model"]["device"] = args.device
    adapter = cfg["model"].get("chronos2", {}).get("adapter")
    if adapter:                 # D136: e.g. model_chronos2_small for autogluon/chronos-2-small
        importlib.import_module(f"tsfm_ad.{adapter}").install()
    if args.cmd in NEEDS_RUN:   # `setup: selected` / `variant.kind: selected`, from selection.csv (D41)
        cfg = resolve_selected(cfg)
    set_seeds(cfg["seed"])
    t0 = time.time()
    code = COMMANDS[args.cmd][0](cfg, args)
    print(f"{args.cmd} done in {time.time() - t0:.1f} s")
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
