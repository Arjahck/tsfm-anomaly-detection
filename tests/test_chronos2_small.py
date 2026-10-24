"""The 13 -> 21 level mapping of chronos-2-small (model_chronos2_small.py, D136): a wrong weight moves every crps and,
if a native level were mapped wrongly, the band score."""
import numpy as np
import pytest
import torch

from tsfm_ad import model_chronos2_small as small
from tsfm_ad.cache import QUANTILE_LEVELS

NATIVE = [0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]   # autogluon/chronos-2-small config.json


def test_native_levels_pass_through_and_missing_ones_sit_halfway():
    W = small.level_weights(NATIVE)
    assert W.shape == (21, 13) and np.allclose(W.sum(axis=1), 1.0)
    q = np.array(NATIVE) * 10.0                    # a value equal to 10 x level makes the expected output exact
    assert np.allclose(W @ q, np.array(QUANTILE_LEVELS) * 10.0)
    for lv in (0.01, 0.05, 0.5, 0.95, 0.99):      # the band and mae scores read only native levels
        i, j = QUANTILE_LEVELS.index(lv), NATIVE.index(lv)
        assert W[i, j] == 1.0 and W[i].sum() == 1.0
    i = QUANTILE_LEVELS.index(0.15)
    assert np.allclose(W[i, NATIVE.index(0.1)], 0.5) and np.allclose(W[i, NATIVE.index(0.2)], 0.5)


def test_no_extrapolation():
    with pytest.raises(ValueError):
        small.level_weights([0.05, 0.5, 0.95])     # 0.01 and 0.99 would lie outside


class _FakePipe:
    quantiles = NATIVE
    model = torch.nn.Linear(1, 1)
    model_context_length = 8192

    def predict(self, inputs, **kw):
        V, H = len(inputs), kw["prediction_length"]
        base = torch.tensor(NATIVE).view(1, 13, 1)
        return [base.expand(1, 13, H) + v for v in range(V)]


def test_wrapper_returns_the_cache_levels_in_the_base_layout():
    w = small.Levels21(_FakePipe())
    assert w.quantiles == list(QUANTILE_LEVELS) and w.model_context_length == 8192
    out = w.predict([0, 1, 2], prediction_length=4)
    assert len(out) == 3 and out[0].shape == (1, 21, 4)
    expect = torch.tensor(QUANTILE_LEVELS, dtype=torch.float32).view(1, 21, 1) + 2
    assert torch.allclose(out[2], expect.expand(1, 21, 4))
