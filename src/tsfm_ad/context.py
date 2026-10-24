"""Context protection: Forecast Fallback (exp 3a) and the frozen reference forecast (exp 3b). PLAN.md 8, D24, D25,
D44, D58.

FF results CSVs and the per-attack FF attribution are in ff_results.py, which is not a forecast source, so
editing them does not change the forecast hash.

Forecast Fallback is our INTERPRETATION of Lowe et al. (`ff-interp-block`). From the paper: the 3-step per-feature
trigger and the 99.5th-percentile per-feature level. Ours: |q50 - y| as the per-step error, thresholds from the base
rolling `calib` cache, the run counter carried across windows, block substitution from the trigger step on, no exit
(or `max_duration`), covariates never substituted.
"""
from __future__ import annotations

import hashlib
import json
from typing import NamedTuple

import numpy as np
import polars as pl

from tsfm_ad import cache
from tsfm_ad.cache import QCOLS

EPISODE_SCHEMA = {"file": pl.String, "channel": pl.String, "start_t": pl.Int64, "end_t": pl.Int64,
                  "n_steps": pl.Int64, "exit": pl.String}


class Episode(NamedTuple):
    channel: int      # row of the hook's (C, H) arrays
    start_t: int      # trigger step = first substituted step
    end_t: int        # last substituted step (inclusive)
    n_steps: int
    exit: str         # max_duration | file_end


def ff_thresholds(calib_df: pl.DataFrame, pct: float = 99.5) -> dict[str, float]:
    """Per-channel tau = the pct-th percentile (linear) of |q50 - y_true| over the rolling calib cache."""
    err = calib_df.select("channel", (pl.col("q50") - pl.col("y_true")).abs().cast(pl.Float64).alias("e"))
    out = err.group_by("channel").agg(pl.col("e").quantile(pct / 100, interpolation="linear")).sort("channel")
    return dict(zip(out["channel"].to_list(), out["e"].to_list()))


def ff_tau(cfg: dict) -> dict[str, float]:
    """FF thresholds of cfg's model and setup, from its base `rolling` calib cache (raises if not run yet)."""
    return ff_thresholds(cache.read(cfg, "calib", variant="rolling"), cfg["variant"]["ff"]["pct"])


def ff_extra(cfg: dict, tau: dict | None = None) -> dict | None:
    """The `extra` that keys an FF cache directory (hash of the thresholds); None for every other kind.

    Readers use it as `cache.read(cfg, split, extra=context.ff_extra(cfg))`.
    """
    if cfg["variant"]["kind"] != "ff":
        return None
    tau = ff_tau(cfg) if tau is None else tau
    blob = json.dumps(sorted(tau.items())).encode()
    return {"ff_tau_sha256": hashlib.sha256(blob).hexdigest()}


class Fallback:
    """The FF hook `hook(o, q50, y) -> mask (C, H)`; state only, it never touches an array (D58).

    Per channel c (row of q50/y) and step t = o + j, in order: an idle channel counts consecutive steps with
    |q50 - y| > tau_c (the count carries across windows); at the k-th it enters fallback, and that step and every
    later step are substituted (mask True) until `max_duration` substituted steps have passed (never, if None).
    After an exit the count restarts at 0. scope "all": a trigger on any channel puts every channel in fallback.
    """

    def __init__(self, tau, k: int = 3, max_duration: int | None = None, scope: str = "feature"):
        if scope not in ("feature", "all"):
            raise ValueError(f"scope must be 'feature' or 'all', got {scope!r}")
        self.tau = np.asarray(tau, dtype=np.float64)
        self.k, self.max_duration, self.scope = k, max_duration, scope
        self.reset()

    def reset(self) -> None:
        """Forget all state and episodes (call at every file start)."""
        c = len(self.tau)
        self.run = np.zeros(c, np.int64)
        self.active = np.zeros(c, bool)
        self.age = np.zeros(c, np.int64)
        self.start = np.full(c, -1, np.int64)
        self.last_t = -1
        self._closed: list[Episode] = []

    def _close(self, chans, t: int, why: str) -> None:
        for c in chans:
            self._closed.append(Episode(int(c), int(self.start[c]), int(t), int(t - self.start[c] + 1), why))
        self.active[chans] = False
        self.age[chans] = 0

    def __call__(self, o: int, q50: np.ndarray, y: np.ndarray) -> np.ndarray:
        exceed = np.abs(np.asarray(q50, np.float64) - y) > self.tau[:, None]
        mask = np.zeros(exceed.shape, bool)
        for j in range(exceed.shape[1]):
            t = o + j
            idle = ~self.active
            self.run = np.where(idle & exceed[:, j], self.run + 1, 0)
            start = idle & (self.run >= self.k)
            if self.scope == "all" and start.any():
                start = idle
            self.start[start] = t
            self.active |= start
            self.run[start] = 0
            mask[:, j] = self.active
            self.age[self.active] += 1
            if self.max_duration:
                self._close(np.flatnonzero(self.active & (self.age >= self.max_duration)), t, "max_duration")
        self.last_t = o + exceed.shape[1] - 1
        return mask

    def episodes(self) -> list[Episode]:
        """Closed episodes plus the ones still active, closed at the last step seen (exit `file_end`)."""
        still = [Episode(int(c), int(self.start[c]), self.last_t, int(self.last_t - self.start[c] + 1), "file_end")
                 for c in np.flatnonzero(self.active)]
        return sorted(self._closed + still, key=lambda e: (e.start_t, e.channel))


def episodes_frame(file: str, episodes: list[Episode], channels: list[str]) -> pl.DataFrame:
    """Episodes of one file with channel names: file, channel, start_t, end_t, n_steps, exit."""
    return pl.DataFrame({
        "file": [file] * len(episodes),
        "channel": [channels[e.channel] for e in episodes],
        "start_t": [e.start_t for e in episodes], "end_t": [e.end_t for e in episodes],
        "n_steps": [e.n_steps for e in episodes], "exit": [e.exit for e in episodes],
    }, schema=EPISODE_SCHEMA)


def frozen_forecast(fc, ref_seg, setup, fcfg, log=None) -> pl.DataFrame:
    """One H-step forecast per group from the whole clean `reference` segment (last `cap` steps), covariates
    included; columns channel, h, q01..q99 (REF_SCHEMA). Exp 3b scores every window against this one band."""
    from tsfm_ad import forecast  # forecast imports this module

    H, L = fcfg["H"], len(ref_seg)
    lo = max(0, L - fcfg["cap"])
    slices = [(ref_seg.rows(g.targets)[:, lo:], ref_seg.rows(g.covariates)[:, lo:] if g.covariates else None)
              for g in setup]
    q = forecast.predict(fc, setup, slices, H, fcfg, log=log)            # (C, H, 21)
    names = [c for g in setup for c in g.targets]
    out = {"channel": np.repeat(np.array(names, dtype=object), H), "h": np.tile(np.arange(1, H + 1), len(names))}
    out.update({col: q[:, :, i].reshape(-1) for i, col in enumerate(QCOLS)})
    return pl.DataFrame(out)
