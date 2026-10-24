"""Chronos-2 (amazon/chronos-2, Apache 2.0) behind the one predict interface of forecast.py (PLAN.md section 14).

Phase 1 runs on Chronos-2 while Timestral is paused (licence, CLAUDE.md; D117). `forecast.predict` calls
`predict_group` once per group and origin; the result has exactly the cache layout: (V, H, 21) float32, rows in
the order of the requested targets, quantiles in the order of `cache.QCOLS` (q01, q05, ..., q95, q99).

- Univariate setups: the V targets go in as V separate items of shape (1, T) (an array (V, 1, T)). Each item gets
  its own group id and the group-attention mask gives other groups exactly zero weight, so no information flows
  between channels (chronos2/dataset.py:253-263, model.py:122-142; checked bit-identical, D119).
  Never a (1, V, T) array (one multivariate item) and never `cross_learning=True`: both let the channels interact.
- Multivariate setups: one item per process group, {"target": (V, T), "past_covariates": {name: (T,)}}. Groups are
  never merged in one item (forecast.predict makes one call per group); covariates are not returned.
- float32 weights, pinned revision, no context longer than the model maximum (the pipeline would cut it silently),
  no horizon beyond one forward pass (`limit_prediction_length=True` raises instead of the autoregressive heuristic).
- Constant rows (a target or covariate whose context holds one value) go in as exact zeros, and a constant target's
  value is added back to its quantiles (D128). Chronos-2 maps a constant row to scale 0 -> eps and scaled 0
  (chronos_bolt.py:95-122), but float32 rounding of the mean often leaves a residual, so the row enters as +0.88,
  -0.88 or 0 (arcsinh(+-1)) depending on the device and the value: on the HAI smoke slice that moved mv-lit targets
  by up to 5.2 z between CPU and MPS (PLAN.md 14.5). Exact zeros give the intended input (scaled 0) on every device
  and at every level; every other row is passed unchanged.
- Quantile crossings are rearranged by sorting (a no-op when the output is monotone; Timestral's output is sorted
  by construction, so the cache contract stays q01 <= ... <= q99).
- `STATS` counts forecasts, rearranged forecasts and constant rows; forecast.predict logs them per call to
  calls_<split>.csv (columns crossed, forecasts, const_rows).

[hashed source]: editing this file changes every Chronos-2 forecast hash (config.MODEL_SOURCES).
"""
from __future__ import annotations

import numpy as np

from tsfm_ad.cache import QUANTILE_LEVELS

STATS = {"forecasts": 0, "crossed": 0, "const_rows": 0}   # (channel, h) forecasts / rearranged ones / constant rows


def load(model_cfg: dict, cache_dir="cache/hf"):
    """Chronos2Pipeline at the pinned revision, float32, on model.device. The base model is built directly
    (Chronos2Model.from_pretrained + Chronos2Pipeline), which is what Chronos2Pipeline.from_pretrained does for a
    base model, minus its unpinned hub lookup of a LoRA adapter on `main` (chronos2/pipeline.py:1158)."""
    from importlib.metadata import version

    import torch
    from chronos.chronos2 import Chronos2Model, Chronos2Pipeline

    c = model_cfg["chronos2"]
    pkg, _, want = c["package"].partition("==")
    if version(pkg) != want:
        raise RuntimeError(f"{pkg} {version(pkg)} is installed, the config pins {c['package']}: run `uv sync`")
    if c.get("dtype", "float32") != "float32":
        raise ValueError("Chronos-2 runs in float32 only (bf16 moves quantiles by up to 0.028, PLAN.md 14)")
    torch.set_num_threads(model_cfg.get("cpu_threads", 4))
    kw = {"revision": c["revision"], "cache_dir": str(cache_dir), "device_map": model_cfg["device"],
          "dtype": torch.float32}
    try:   # the pinned weights are usually in cache/hf already: no network call then (D101)
        model = Chronos2Model.from_pretrained(c["repo"], local_files_only=True, **kw)
    except (OSError, ValueError):
        model = Chronos2Model.from_pretrained(c["repo"], **kw)
    pipe = Chronos2Pipeline(model=model.eval())
    check(pipe, model_cfg["max_context"])
    return pipe


def check(pipe, max_context: int) -> None:
    """The loaded model must match what the cache and the config assume: 21 levels in cache order, float32
    weights, and a context maximum equal to model.max_context."""
    levels = tuple(round(float(q), 4) for q in pipe.quantiles)
    if levels != tuple(round(q, 4) for q in QUANTILE_LEVELS):
        raise ValueError(f"Chronos-2 quantile levels {levels} differ from the cache levels {QUANTILE_LEVELS}")
    dtypes = {p.dtype for p in pipe.model.parameters()}
    if {str(d) for d in dtypes} != {"torch.float32"}:
        raise ValueError(f"Chronos-2 weights are {dtypes}, expected float32 only")
    if pipe.model_context_length != max_context:
        raise ValueError(f"Chronos-2 context maximum is {pipe.model_context_length}, model.max_context says "
                         f"{max_context}")


def predict_group(pipe, tgt: np.ndarray, cov: np.ndarray | None, H: int, multivariate: bool) -> np.ndarray:
    """Quantiles (V, H, 21) of one group: tgt (V, T) targets, cov (C, T) past-only covariates or None."""
    import torch

    V, T = tgt.shape
    if T > pipe.model_context_length:
        raise ValueError(f"context of {T} steps exceeds the Chronos-2 maximum {pipe.model_context_length}; "
                         "cap the context (forecast.cap) instead of letting the model cut it")
    tgt, shift = _zero_constant_rows(tgt)
    kw = {"prediction_length": H, "cross_learning": False, "limit_prediction_length": True}
    if multivariate:
        item = {"target": tgt}
        if cov is not None and len(cov):
            cov, _ = _zero_constant_rows(cov)
            item["past_covariates"] = {f"cov{j:03d}": cov[j] for j in range(len(cov))}
        out = pipe.predict([item], **kw)
        if len(out) != 1:
            raise ValueError(f"one multivariate item gave {len(out)} outputs")
        q = out[0]                                      # (V, 21, H)
    else:
        if cov is not None and len(cov):
            raise ValueError("univariate setups take no covariates")
        out = pipe.predict(tgt[:, None, :], **kw)       # V items of 1 variate: V groups, no cross-group attention
        if len(out) != V or any(o.shape[0] != 1 for o in out):
            raise ValueError(f"{V} univariate items gave outputs of shapes {[tuple(o.shape) for o in out]}")
        q = torch.cat(out)                              # (V, 21, H), item order = row order
    q = q.permute(0, 2, 1).numpy().astype(np.float32, copy=False)   # (V, H, 21): time before quantile
    if q.shape != (V, H, len(QUANTILE_LEVELS)):
        raise ValueError(f"Chronos-2 output shape {q.shape}, expected {(V, H, len(QUANTILE_LEVELS))}")
    if not np.isfinite(q).all():
        raise ValueError("Chronos-2 returned non-finite quantiles")
    crossed = (np.diff(q, axis=-1) < 0).any(axis=-1)
    STATS["forecasts"] += crossed.size
    if crossed.any():
        STATS["crossed"] += int(crossed.sum())
        q = np.sort(q, axis=-1)
    if shift.any():
        q = q + shift[:, None, None]                    # constant targets: back to their value (others + 0.0)
    return q


def _zero_constant_rows(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(x with every constant row replaced by exact zeros, the per-row shift: the constant, or 0 for other rows)."""
    x = np.ascontiguousarray(x, dtype=np.float32)
    const = (x == x[:, :1]).all(axis=1)
    shift = np.where(const, x[:, 0], 0).astype(np.float32)
    if const.any():
        STATS["const_rows"] += int(const.sum())
        x = x.copy()
        x[const] = 0.0
    return x, shift
