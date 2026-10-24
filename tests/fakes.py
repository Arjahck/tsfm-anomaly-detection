"""A fake Chronos2Pipeline for download-free tests (no model, no weights).

It applies the input checks of the real `Chronos2Pipeline.predict` that the adapter relies on (a 3-D array, or a
list of dicts with 1-D past covariates exactly as long as the target), records every call, and returns one tensor
(V, 21, H) per item like the real one. Quantile i of variate v at horizon step h is
`last value of v + (level_i - 0.5) * (1 + h) / 10`: q50 is the last context value, the levels are increasing, and
every value tells which item, variate, level and step it belongs to.
"""
import numpy as np
import torch

from tsfm_ad.cache import QUANTILE_LEVELS


def fake_quantiles(target: np.ndarray, H: int) -> np.ndarray:
    """(V, 21, H) quantiles of the fake for a (V, T) target."""
    lv = np.asarray(QUANTILE_LEVELS)[None, :, None] - 0.5
    return (target[:, -1][:, None, None] + lv * (1 + np.arange(H))[None, None, :] / 10).astype(np.float32)


class FakeChronos2:
    model_context_length = 8192
    quantiles = list(QUANTILE_LEVELS)

    def __init__(self):
        self.calls = []
        self.model = torch.nn.Linear(1, 1)      # float32 parameters, for model_chronos2.check

    def predict(self, inputs, prediction_length=None, batch_size=256, context_length=None, cross_learning=False,
                limit_prediction_length=False):
        H = prediction_length
        if isinstance(inputs, (np.ndarray, torch.Tensor)):
            x = np.asarray(inputs, np.float32)
            if x.ndim != 3:
                raise ValueError(f"Expected 3-d tensor, got {x.ndim}-d")
            items = [{"target": x[i].copy(), "cov": {}} for i in range(len(x))]
        else:
            items = []
            for d in inputs:
                t = np.asarray(d["target"], np.float32)
                t = t[None] if t.ndim == 1 else t
                cov = {k: np.asarray(v, np.float32).copy() for k, v in d.get("past_covariates", {}).items()}
                if any(v.ndim != 1 or len(v) != t.shape[1] for v in cov.values()):
                    raise ValueError("past covariates must be 1-D and as long as the target")
                items.append({"target": t.copy(), "cov": cov})
        self.calls.append({"items": items, "H": H, "array_input": isinstance(inputs, (np.ndarray, torch.Tensor)),
                           "cross_learning": cross_learning, "limit_prediction_length": limit_prediction_length})
        return [torch.from_numpy(fake_quantiles(it["target"], H)) for it in items]
