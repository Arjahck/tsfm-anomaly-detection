"""The D21 selection rule on hand-made metrics.csv files (PLAN.md section 8, D40, D84, D85), and the in-memory
resolution of `setup: selected` / `variant.kind: selected` (D41)."""
import copy
import json
from pathlib import Path

import polars as pl
import pytest

from tsfm_ad import cache, config, selection
from tsfm_ad.config import load_config, resolve_selected

ROOT = Path(__file__).resolve().parents[1]

M, M5, D = "timestral-28M-49b2640-cpu", "timestral-5M-bdd20cf-cpu", "hai2103-10s"
C2 = "chronos2-29ec376-mps"                      # the model of configs/base.yaml (D117, D130)
RULE = {"metric": "pr_auc", "tiebreak": "roc_auc", "agg": "topk"}


def row(model, setup, variant, cs, score, pr, roc, agg="topk", cal="calib", h="abcd1234"):
    return {"run_key": f"{D}/{model}/{setup}/{variant}", "hash8": h, "channel_set": cs, "score": score, "agg": agg,
            "calib_source": cal, "roc_auc": roc, "pr_auc": pr}


ROWS = [row(M, "uni", "rolling", "mvlit34", "band", 0.30, 0.80), row(M, "mv-lit", "rolling", "mvlit34", "band", 0.30, 0.79),
        row(M, "uni", "rolling", "uni51", "band", 0.35, 0.81),
        row(M, "uni", "rolling", "mvlit34", "band", 0.30, 0.80, cal="calib2"),
        row(M, "uni", "rolling", "mvlit34", "band", 0.9, 0.9, agg="max"),
        row(M5, "uni", "rolling", "mvlit34", "band", 0.9, 0.9), row(M5, "mv-lit", "rolling", "mvlit34", "band", 0.95, 0.9),
        row(M, "uni", "ff-interp-block", "uni51", "band", 0.36, 0.7), row(M, "uni", "frozen", "uni51", "band", 0.36, 0.75),
        row(M, "uni", "dual", "uni51", "dual", 0.2, 0.6), row(M, "uni", "dual", "uni51", "band", 0.99, 0.99),
        row(M, "uni", "ff-interp-block-max60-testinf", "uni51", "band", 0.5, 0.9)]


def test_base_and_best_follow_d21(tmp_path):
    pl.DataFrame(ROWS).write_csv(tmp_path / "metrics.csv")
    selection.select("base", tmp_path / "metrics.csv", RULE)            # two models qualify: 28M decides (D84)
    b = selection.selected("base", tmp_path / "selection.csv")
    assert (b["setup"], b["channel_set"], b["model"]) == ("uni", "uni51", M)   # PR tie, uni wins on ROC
    selection.select("best", tmp_path / "metrics.csv", RULE)
    s = selection.selected("best", tmp_path / "selection.csv")
    assert (s["variant"], s["kind"]) == ("frozen", "frozen")   # PR tie with ff; frozen has the higher ROC; the
    sel = pl.read_csv(tmp_path / "selection.csv")              # dual run competes with its dual score, max60 never
    assert sel.filter(pl.col("candidate_run_key").str.contains("max60"))["rank"].is_null().all()
    assert (sel["note"].str.contains("picked on test results")).all()


def test_rule_for_restricts_to_the_config_model(tmp_path):
    pl.DataFrame(ROWS).write_csv(tmp_path / "metrics.csv")
    cfg = {"selection": RULE, "dataset": {"key": D},
           "model": {"name": "timestral", "size": "5M", "device": "cpu",
                     "revisions": {"5M": "bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f"}}}
    selection.select("base", tmp_path / "metrics.csv", selection.rule_for(cfg))
    assert selection.selected("base", tmp_path / "selection.csv")["setup"] == "mv-lit"   # 5M: mv-lit is better


def test_strictly_better_mv_lit_wins_and_a_stale_best_is_refused(tmp_path):
    pl.DataFrame(ROWS).write_csv(tmp_path / "metrics.csv")
    selection.select("base", tmp_path / "metrics.csv", RULE)
    selection.select("best", tmp_path / "metrics.csv", RULE)
    pl.DataFrame(ROWS[:1] + [row(M, "mv-lit", "rolling", "mvlit34", "band", 0.31, 0.5)]).write_csv(tmp_path / "metrics.csv")
    selection.select("base", tmp_path / "metrics.csv", RULE)
    assert selection.selected("base", tmp_path / "selection.csv")["channel_set"] == "mvlit34"
    with pytest.raises(LookupError):              # the best pick was made on the old base
        selection.selected("best", tmp_path / "selection.csv")
    with pytest.raises(ValueError):               # no mv-lit ff/frozen/dual rows: never a pick on a partial set
        selection.select("best", tmp_path / "metrics.csv", RULE)


def test_resolve_selected_reads_the_config_results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(selection, "check_pick", lambda pick, cfg: None)   # hand-made rows: no cache to check
    pl.DataFrame(ROWS).write_csv(tmp_path / "metrics.csv")
    selection.select("base", tmp_path / "metrics.csv", RULE)
    selection.select("best", tmp_path / "metrics.csv", RULE)
    cfg = {"paths": {"results": str(tmp_path)}, "setup": "selected", "selection_stage": "best",
           "variant": {"kind": "selected"}}
    out = resolve_selected(copy.deepcopy(cfg))
    assert (out["setup"], out["variant"]["kind"]) == ("uni", "frozen") and cfg["setup"] == "selected"
    with pytest.raises(ValueError):
        resolve_selected({**cfg, "selection_stage": "base"})


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """base.yaml (Chronos-2) on a tmp cache whose uni and mv-lit rolling run directories exist (no forecasts)."""
    monkeypatch.setitem(config.MODEL_SOURCES, "chronos2", ("config.py",))
    cfg = load_config(ROOT / "configs" / "base.yaml")
    cfg["paths"].update(cache=str(tmp_path / "cache"), results=str(tmp_path / "results"))
    prep = tmp_path / "cache" / D / "prepared"
    prep.mkdir(parents=True)
    (prep / "manifest.json").write_text(json.dumps({"digest": "x"}))
    h = {}
    for setup in ("uni", "mv-lit"):
        c = copy.deepcopy(cfg)
        c["setup"] = setup
        d = cache.run_dir(c)
        d.mkdir(parents=True)
        h[setup] = d.name.split("@")[1]
    return cfg, h


def test_select_refuses_rows_of_another_forecast_hash_and_forgets_the_old_pick(runs):
    """D113: a stale metrics row never takes part in a pick, and a failed select leaves no pick behind."""
    cfg, h = runs
    res = Path(cfg["paths"]["results"])
    res.mkdir()
    good = [row(C2, "uni", "rolling", "mvlit34", "band", 0.30, 0.80, h=h["uni"]),
            row(C2, "mv-lit", "rolling", "mvlit34", "band", 0.40, 0.79, h=h["mv-lit"]),
            row(M, "mv-lit", "rolling", "mvlit34", "band", 0.99, 0.99, h="0000aaaa")]   # another model: ignored
    pl.DataFrame(good).write_csv(res / "metrics.csv")
    selection.select("base", res / "metrics.csv", selection.rule_for(cfg), cfg)
    assert selection.selected("base", res / "selection.csv")["setup"] == "mv-lit"
    sel = copy.deepcopy(cfg)
    sel["setup"] = "selected"
    assert resolve_selected(sel)["setup"] == "mv-lit"
    stale = [good[0], row(C2, "mv-lit", "rolling", "mvlit34", "band", 0.40, 0.79, h="deadbeef")]
    pl.DataFrame(stale).write_csv(res / "metrics.csv")
    with pytest.raises(ValueError, match="not from the current forecasts"):
        selection.select("base", res / "metrics.csv", selection.rule_for(cfg), cfg)
    with pytest.raises(LookupError):                       # the earlier pick was removed
        selection.selected("base", res / "selection.csv")


def test_a_pick_made_on_older_forecasts_is_refused(runs):
    cfg, h = runs
    res = Path(cfg["paths"]["results"])
    res.mkdir()
    pl.DataFrame([row(C2, "uni", "rolling", "mvlit34", "band", 0.50, 0.80, h=h["uni"]),
                  row(C2, "mv-lit", "rolling", "mvlit34", "band", 0.40, 0.79, h=h["mv-lit"])]
                 ).write_csv(res / "metrics.csv")
    selection.select("base", res / "metrics.csv", selection.rule_for(cfg), cfg)
    sel = copy.deepcopy(cfg)
    sel["setup"] = "selected"
    sel["forecast"]["W_s"] += 100                          # a forecast setting changed: new hashes, no forecasts yet
    with pytest.raises(LookupError, match="not current"):
        resolve_selected(sel)
