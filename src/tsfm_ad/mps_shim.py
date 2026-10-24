"""UNOFFICIAL workaround so timestral 1.0.0 (commit a534bdb) runs on Apple MPS (PLAN.md 2.1, 6, D15, D54).

MPS has no float64, and timestral computes three things in float64 on the model's device:
- `scaler.compute_causal_statistics` (scaler.py:29-30): causal running mean/std, on every call;
- `TimestralForecaster._refine_block` (forecaster.py:472, scaler.advancing_block_frames): only when a decode
  block has more than one 32-step patch (horizon > 32, e.g. cf-onset);
- `TimestralForecaster._encode_categorical` (forecaster.py:265): categorical covariates with one target (unused).
`install()` makes exactly those three run on CPU in float64 and moves the results back to MPS. The transformer stays
on MPS in float32. Upstream does not support MPS (GitHub issue #4), so every (size, setup) run on MPS is checked
against CPU on the smoke slice first (D54). This is our own re-implementation of the planning probe's shim.
"""
from __future__ import annotations

import timestral.forecaster as _forecaster
import timestral.scaler as _scaler

_originals: dict = {}


def _on_mps(x) -> bool:
    return x is not None and x.device.type == "mps"


def _causal_statistics(data, observation_mask, *args, **kwargs):
    orig = _originals["compute_causal_statistics"]
    if not _on_mps(data):
        return orig(data, observation_mask, *args, **kwargs)
    means, scales = orig(data.cpu(), observation_mask.cpu(), *args, **kwargs)
    return means.to(data.device), scales.to(data.device)


def _refine_block(self, quantiles, context, mask, target_rows):
    orig = _originals["_refine_block"]
    if not _on_mps(quantiles):
        return orig(self, quantiles, context, mask, target_rows)
    # model.scale (called inside) uses no parameters, so the whole refine can run on CPU.
    out = orig(self, quantiles.cpu(), context.cpu(), mask.cpu(), None if target_rows is None else target_rows.cpu())
    return out.to(quantiles.device)


def _encode_categorical(self, codes, target_context):
    if _on_mps(target_context):
        target_context = target_context.cpu()
    return _originals["_encode_categorical"](self, codes, target_context)


def installed() -> bool:
    return bool(_originals)


def install() -> None:
    """Patch the three float64 sites. Idempotent: a second call does nothing."""
    if _originals:
        return
    cls = _forecaster.TimestralForecaster
    _originals["compute_causal_statistics"] = _scaler.compute_causal_statistics
    _originals["_refine_block"] = cls._refine_block
    _originals["_encode_categorical"] = cls._encode_categorical
    # causal_patch_loc_scale looks compute_causal_statistics up in the scaler module at call time.
    _scaler.compute_causal_statistics = _causal_statistics
    cls._refine_block = _refine_block
    cls._encode_categorical = _encode_categorical
