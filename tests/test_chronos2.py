"""The Chronos-2 adapter (PLAN.md 14, D117-D120): quantile column order, channel order, univariate independence,
the multivariate item, the Timestral guard and the Chronos-2 configs. No download: a fake pipeline (tests/fakes.py),
a tiny randomly initialised Chronos2Model (the real architecture and group-attention mask, no weights), and the
pinned weights only when they are already in cache/hf."""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest
import torch

from fakes import FakeChronos2, fake_quantiles
from tsfm_ad import config, forecast, model_chronos2, pipeline, selection
from tsfm_ad.cache import QCOLS, QUANTILE_LEVELS
from tsfm_ad.config import load_config
from tsfm_ad.data import Group

ROOT = Path(__file__).resolve().parents[1]
UNI = {"model": "chronos2", "multivariate": False}
MV = {"model": "chronos2", "multivariate": True}
REV = "29ec3766d36d6f73f0696f85560a422f50e8498c"
WEIGHTS = ROOT / "cache" / "hf" / "models--amazon--chronos-2" / "snapshots" / REV / "model.safetensors"


def series(n, T, seed=0):
    return np.random.default_rng(seed).normal(size=(n, T)).astype(np.float32).cumsum(1)


def test_cache_columns_are_the_21_chronos2_levels_in_order():
    assert QCOLS == ["q01", "q05", "q10", "q15", "q20", "q25", "q30", "q35", "q40", "q45", "q50", "q55", "q60",
                     "q65", "q70", "q75", "q80", "q85", "q90", "q95", "q99"]
    assert [QCOLS.index(c) for c in ("q05", "q50", "q95")] == [1, 10, 19]
    model_chronos2.check(FakeChronos2(), 8192)
    small = FakeChronos2()                       # chronos-2-small: 13 native levels, not the cache's 21
    small.quantiles = [0.01, 0.05] + [round(0.1 * i, 1) for i in range(1, 10)] + [0.95, 0.99]
    with pytest.raises(ValueError, match="quantile levels"):
        model_chronos2.check(small, 8192)


def test_univariate_quantile_and_channel_order():
    fake, X = FakeChronos2(), series(4, 50)
    q = forecast.predict(fake, [Group("all", list("abcd"), [])], [(X, None)], 30, UNI)
    assert q.shape == (4, 30, 21) and q.dtype == np.float32
    call = fake.calls[0]
    assert call["array_input"] and len(call["items"]) == 4                    # 4 items of one variate each
    assert all(it["target"].shape == (1, 50) for it in call["items"])
    assert not call["cross_learning"] and call["limit_prediction_length"]
    for v in range(4):                                                          # row v = channel v, column i = level i
        assert np.array_equal(call["items"][v]["target"][0], X[v])
        assert np.array_equal(q[v], fake_quantiles(X[v:v + 1], 30)[0].T)
    assert np.array_equal(q[:, :, QCOLS.index("q50")], np.repeat(X[:, -1:], 30, axis=1))
    lv = (q - X[:, -1][:, None, None]) / ((1 + np.arange(30))[None, :, None] / 10) + 0.5
    assert np.allclose(lv, np.broadcast_to(QUANTILE_LEVELS, lv.shape), atol=1e-3)   # q05 holds level 0.05, ...


def test_multivariate_one_item_per_group_covariates_past_only():
    fake, X = FakeChronos2(), series(6, 40, seed=1)
    groups = [Group("P1", ["a", "b"], ["d", "e", "f"]), Group("P2", ["c"], [])]
    q = forecast.predict(fake, groups, [(X[:2], X[3:6]), (X[2:3], None)], 30, MV)
    assert q.shape == (3, 30, 21) and len(fake.calls) == 2                     # never merged: one call per group
    p1, p2 = fake.calls
    assert not p1["array_input"] and len(p1["items"]) == 1 and p1["items"][0]["target"].shape == (2, 40)
    cov = p1["items"][0]["cov"]
    assert len(cov) == 3 and all(np.array_equal(cov[k], X[3 + j]) for j, k in enumerate(sorted(cov)))
    assert p2["items"][0]["cov"] == {}
    assert np.array_equal(q, np.concatenate([fake_quantiles(X[:2], 30), fake_quantiles(X[2:3], 30)]).transpose(0, 2, 1))


def test_crossing_rearranged_and_context_cap_enforced():
    class Crossing(FakeChronos2):
        def predict(self, inputs, **k):
            out = super().predict(inputs, **k)
            out[0][0, [3, 4], 0] = out[0][0, [4, 3], 0]        # swap two levels at h = 1 of the first item
            return out

    before = model_chronos2.STATS["crossed"]
    q = forecast.predict(Crossing(), [Group("all", ["a", "b"], [])], [(series(2, 20), None)], 30, UNI)
    assert (np.diff(q, axis=-1) >= 0).all() and model_chronos2.STATS["crossed"] == before + 1
    with pytest.raises(ValueError, match="exceeds the Chronos-2 maximum"):
        forecast.predict(FakeChronos2(), [Group("all", ["a"], [])], [(series(1, 8193), None)], 30, UNI)


def test_constant_rows_enter_as_exact_zeros_and_targets_are_shifted_back():
    fake, X = FakeChronos2(), series(5, 40, seed=3)
    X[1], X[3] = 0.43639088, -1.1848395                      # a constant target and a constant covariate (HAI values)
    before = model_chronos2.STATS["const_rows"]
    q = forecast.predict(fake, [Group("P1", ["a", "b", "c"], ["d", "e"])], [(X[:3], X[3:])], 30, MV)
    item = fake.calls[0]["items"][0]
    assert (item["target"][1] == 0).all() and np.array_equal(item["target"][[0, 2]], X[[0, 2]])
    assert (item["cov"]["cov000"] == 0).all() and np.array_equal(item["cov"]["cov001"], X[4])
    assert model_chronos2.STATS["const_rows"] == before + 2
    assert np.allclose(q[1, :, QCOLS.index("q50")], 0.43639088) and np.array_equal(
        q[0], fake_quantiles(X[:1], 30)[0].T)


def test_a_constant_covariate_no_longer_depends_on_its_level():
    """Chronos-2 scales a constant row by the float32 rounding residual of its mean, so without the guard its level
    decides whether it enters as +-0.88 or 0 (D128). With the guard every level gives the same bits."""
    pipe, X = tiny_pipeline(), series(3, 120, seed=4)
    outs = []
    for level in (0.0, 0.43639088, -1.1848395, 12.0189):
        cov = np.full((1, 120), level, np.float32)
        outs.append(forecast.predict(pipe, [Group("P1", ["a", "b"], ["c"])], [(X[:2], cov)], 30, MV))
    assert all(np.array_equal(o, outs[0]) for o in outs[1:])


def tiny_pipeline():
    """The real Chronos-2 architecture (group attention, instance norm, quantile head) with random weights."""
    from chronos.chronos2 import Chronos2Model, Chronos2Pipeline
    from chronos.chronos2.config import Chronos2CoreConfig

    torch.manual_seed(0)
    cfg = Chronos2CoreConfig(d_model=32, d_kv=8, d_ff=64, num_layers=2, num_heads=4, dropout_rate=0.0,
                             initializer_factor=0.3, chronos_config={
                                 "context_length": 256, "input_patch_size": 16, "input_patch_stride": 16,
                                 "output_patch_size": 16, "max_output_patches": 4, "quantiles": list(QUANTILE_LEVELS),
                                 "use_arcsinh": True, "use_reg_token": True, "time_encoding_scale": 256})
    return Chronos2Pipeline(model=Chronos2Model(cfg).eval())


def independence(pipe, n=6, T=200):
    """Rows 1..n-1 forecast through the adapter with series 0 unchanged vs perturbed three ways."""
    X = series(n, T, seed=2)
    g = [Group("all", [f"c{i}" for i in range(n)], [])]
    ref = forecast.predict(pipe, g, [(X, None)], 30, UNI)
    for change in (lambda x: x * 50 + 100, lambda x: x + 30 * (np.arange(T) >= T - 40), lambda x: -x[::-1]):
        Y = X.copy()
        Y[0] = change(Y[0])
        out = forecast.predict(pipe, g, [(Y, None)], 30, UNI)
        assert not np.array_equal(out[0], ref[0])
        assert np.array_equal(out[1:], ref[1:])                               # bit-identical: no information flow
    return X


def test_univariate_rows_are_independent_in_the_real_architecture():
    pipe = tiny_pipeline()
    X = independence(pipe)
    Y = X.copy()
    Y[0] = Y[0] * 50 + 100     # control: the cross-learning mode the adapter never uses does mix the rows
    a = torch.stack(pipe.predict(X[:, None, :], prediction_length=30, cross_learning=True))
    b = torch.stack(pipe.predict(Y[:, None, :], prediction_length=30, cross_learning=True))
    assert (a[1:] - b[1:]).abs().max() > 1e-6


@pytest.mark.skipif(not WEIGHTS.exists(), reason="amazon/chronos-2 weights are not in cache/hf (no download here)")
def test_univariate_rows_are_independent_with_the_pinned_weights():
    cfg = load_config(ROOT / "configs" / "base.yaml")
    m = {**cfg["model"], "device": "cpu"}
    independence(model_chronos2.load(m, ROOT / "cache" / "hf"))


def test_timestral_is_refused_without_the_permission_switch(monkeypatch):
    monkeypatch.delenv("TSFM_ALLOW_TIMESTRAL", raising=False)
    cfg = load_config(ROOT / "configs" / "timestral" / "exp4_5m.yaml")
    assert cfg["model"]["name"] == "timestral"
    with pytest.raises(RuntimeError, match="licence pause, see CLAUDE.md"):
        forecast.load_forecaster(cfg["model"], ROOT / "cache" / "hf")


def test_configs_run_chronos2_and_all_skips_the_timestral_folder():
    for p in sorted((ROOT / "configs").glob("*.yaml")):
        c = load_config(p)
        assert c["model"]["name"] in ("chronos2", "baseline"), p.name
        assert c["forecast"]["cap"] <= c["model"]["max_context"] == 8192, p.name
    base = load_config(ROOT / "configs" / "base.yaml")
    assert base["forecast"]["cap"] == 8192 and base["model"]["chronos2"]["revision"] == REV
    for p in sorted((ROOT / "configs" / "timestral").glob("*.yaml")):
        c = load_config(p)
        assert c["model"]["name"] == "timestral" and c["model"]["max_context"] == 32768, p.name
    loaded = re.findall(r'r\.load\(f?"([^"]+)"\)', Path(pipeline.__file__).read_text())
    loaded += re.findall(r'\("(\w+\.yaml)", "exp', Path(pipeline.__file__).read_text())
    assert loaded and all("/" not in n and (ROOT / "configs" / n).exists() for n in loaded), loaded


def test_model_tag_hash_and_run_key_parsing(tmp_path):
    cfg = load_config(ROOT / "configs" / "base.yaml")
    cfg["paths"]["cache"] = str(tmp_path)
    (tmp_path / cfg["dataset"]["key"] / "prepared").mkdir(parents=True)
    (tmp_path / cfg["dataset"]["key"] / "prepared" / "manifest.json").write_text(json.dumps({"digest": "x"}))
    assert config.model_tag(cfg) == "chronos2-29ec376-mps" and config.model_params(cfg) == 119477664
    s = config.forecast_settings(cfg)
    assert "symmetric_averaging" not in s["forecast"] and s["model"]["dtype"] == "float32"
    other = copy.deepcopy(cfg)
    other["forecast"]["symmetric_averaging"] = False                         # a Timestral flag: no new hash
    assert config.forecast_hash(other) == config.forecast_hash(cfg)
    other["model"]["chronos2"]["revision"] = "f" * 40
    assert config.forecast_hash(other) != config.forecast_hash(cfg)
    c = selection.run_cfg(cfg, "hai2103-10s/chronos2-29ec376-mps/mv-lit/ff-interp-block-max60-testinf@abcd1234")
    assert (c["model"]["name"], c["model"]["device"], c["setup"], c["variant"]["kind"]) == ("chronos2", "mps",
                                                                                           "mv-lit", "ff")
    with pytest.raises(ValueError):
        selection.run_cfg(cfg, "hai2103-10s/chronos2-0000000-cpu/uni/rolling")   # another revision
