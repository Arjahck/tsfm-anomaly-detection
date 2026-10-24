"""chronos-2-small (autogluon/chronos-2-small, Apache 2.0, 27.9M parameters) through the unchanged Chronos-2 adapter
(PLAN.md D136; Arthur's go for Q19 on 2026-10-20).

The small checkpoint has 13 quantile levels (0.01, 0.05, 0.1, 0.2, ..., 0.8, 0.9, 0.95, 0.99; its config.json); the
cache has 21. The 8 missing levels (0.15, 0.25, ..., 0.85) lie between native neighbours and are interpolated
linearly in the level. q01, q05, q50, q95 and q99 are native, so the band and mae scores do not depend on the
interpolation; crps uses all 21 levels and does (INTERPRETATION, REPORT.md).

`install()` makes `model_chronos2.load` return a wrapper with the 21 cache levels for this repo only; every other repo
loads exactly as before. model_chronos2.py and forecast.py stay byte-identical, so no amazon/chronos-2 cache key
changes. The CLI installs it when `model.chronos2.adapter` names this module.

[hashed source] for the small model only (config.model_sources).
"""
from __future__ import annotations

import numpy as np

from tsfm_ad import model_chronos2
from tsfm_ad.cache import QUANTILE_LEVELS

SMALL_REPO = "autogluon/chronos-2-small"
_ORIG_LOAD = model_chronos2.load


def level_weights(native, target=QUANTILE_LEVELS) -> np.ndarray:
    """(len(target), len(native)) matrix W with W @ q_native = q_target: linear in the level between the two native
    neighbours. Every target level must lie inside the native range (no extrapolation)."""
    nat = np.asarray(native, np.float64)
    if (np.diff(nat) <= 0).any():
        raise ValueError(f"native levels {native} are not increasing")
    W = np.zeros((len(target), len(nat)))
    for i, q in enumerate(target):
        if q < nat[0] - 1e-9 or q > nat[-1] + 1e-9:
            raise ValueError(f"level {q} lies outside the native range {nat[0]}-{nat[-1]}")
        j = int(np.searchsorted(nat, q - 1e-9))
        if abs(nat[j] - q) < 1e-9:
            W[i, j] = 1.0
        else:
            w = (q - nat[j - 1]) / (nat[j] - nat[j - 1])
            W[i, j - 1], W[i, j] = 1.0 - w, w
    return W


class Levels21:
    """A Chronos2Pipeline whose `predict` returns the 21 cache levels: (V, 21, H) per item, like the base model."""

    def __init__(self, pipe):
        import torch

        self._pipe = pipe
        self._W = torch.tensor(level_weights([float(q) for q in pipe.quantiles]), dtype=torch.float32)
        self.quantiles = list(QUANTILE_LEVELS)
        self.model = pipe.model
        self.model_context_length = pipe.model_context_length

    def predict(self, inputs, **kw):
        import torch

        return [torch.einsum("lk,vkh->vlh", self._W.to(o.device), o.to(torch.float32)).cpu()
                for o in self._pipe.predict(inputs, **kw)]


def load(model_cfg: dict, cache_dir="cache/hf"):
    """The small model wrapped to the cache levels; any other repo goes to the original loader unchanged."""
    if model_cfg["chronos2"]["repo"] != SMALL_REPO:
        return _ORIG_LOAD(model_cfg, cache_dir)
    check = model_chronos2.check
    model_chronos2.check = lambda pipe, max_context: None     # the 13-level check runs on the wrapper below
    try:
        pipe = _ORIG_LOAD(model_cfg, cache_dir)
    finally:
        model_chronos2.check = check
    wrapped = Levels21(pipe)
    check(wrapped, model_cfg["max_context"])
    return wrapped


def install() -> None:
    model_chronos2.load = load
