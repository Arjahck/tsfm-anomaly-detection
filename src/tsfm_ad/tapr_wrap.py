"""Official TaPR (vendor/TaPR/TaPR.py, unmodified) called in memory (PLAN.md section 9, D30, D31).

The vendored file is loaded by path and its sha256 is checked. Its file loaders are never used: they invent a
whole-series prediction when a detector never fires (bugs B1/B2 in research/tapr.md). Ranges are built here from
0/1 arrays instead. F1 = 2 TaP TaR / (TaP + TaR) is ours; TaPR.py does not compute it.
"""
from __future__ import annotations

import hashlib
import importlib.util
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TAPR_PATH = "vendor/TaPR/TaPR.py"
TAPR_SHA256 = "0ada5df354e6f8d06581c5b19eaf659cee656be8c0f3a22ac32f55c66e74b6b1"


@lru_cache(maxsize=None)
def load_official(path: str = TAPR_PATH):
    """Import the vendored TaPR.py as a module; a relative path is taken from the project root."""
    p = Path(path)
    p = p if p.is_absolute() else ROOT / p
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != TAPR_SHA256:
        raise RuntimeError(f"{p} sha256 {digest} is not the vendored official TaPR.py ({TAPR_SHA256})")
    spec = importlib.util.spec_from_file_location("tapr_official", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def runs(b) -> list[tuple[int, int]]:
    """Inclusive (first, last) index pairs of the runs of 1 in a 0/1 array."""
    d = np.diff(np.concatenate(([0], (np.asarray(b).ravel() != 0).astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1).tolist(), (np.flatnonzero(d == -1) - 1).tolist()))


def _evaluator(mod, anomalies, predictions, theta, delta):
    ev = mod.TaPR([1, -1], theta, delta)  # the label pair only matters for the file loaders, which are not used
    ev._anomalies = [mod.Term(s, e, str(i)) for i, (s, e) in enumerate(anomalies)]
    ev._gen_ambiguous()                   # the delta-long ambiguous zone after each anomaly
    ev._predictions = [mod.Term(s, e, str(i)) for i, (s, e) in enumerate(predictions)]
    return ev


def tapr(y_true, y_pred, theta=0.5, delta=0, alpha=0.5, theta_r=None, theta_p=None) -> dict:
    """Official TaPR on 0/1 arrays (1 = attack / alarm). delta is in steps.

    theta_r / theta_p (HAICon-like config) override theta for TaR / TaP; two TaPR objects are used then, because
    TaPR.py has a single theta. Detection uses `>` theta as in the official code (TaPR.py:155, 178).
    """
    if int(delta) != delta or delta < 0 or delta == 1:
        raise ValueError(f"delta must be an integer >= 0 and != 1 (TaPR.py divides by zero at 1), got {delta}")
    anomalies, predictions = runs(y_true), runs(y_pred)
    short = [(s, e) for s, e in anomalies if e - s + 1 < 2]
    if short:
        raise ValueError(f"anomaly ranges of length 1 crash TaPR.py: {short[:5]}")
    mod = load_official()
    th_r = theta if theta_r is None else theta_r
    th_p = theta if theta_p is None else theta_p
    ev_r = _evaluator(mod, anomalies, predictions, th_r, int(delta))
    ev_p = ev_r if th_p == th_r else _evaluator(mod, anomalies, predictions, th_p, int(delta))
    tar_d, _ = ev_r.TaR_d()
    tar_p = ev_r.TaR_p()
    tap_d, _ = ev_p.TaP_d()
    tap_p = ev_p.TaP_p()
    tar = alpha * tar_d + (1 - alpha) * tar_p   # same combination as TaPR.py main()
    tap = alpha * tap_d + (1 - alpha) * tap_p
    f1 = 0.0 if tar + tap == 0 else 2 * tap * tar / (tap + tar)
    return {"TaP": tap, "TaP_d": tap_d, "TaP_p": tap_p, "TaR": tar, "TaR_d": tar_d, "TaR_p": tar_p, "F1": f1,
            "n_pred_ranges": len(predictions), "n_anomalies": len(anomalies)}


def join_files(pairs, gap: int) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate per-file (y_true, y_pred) arrays with `gap` normal steps between files (gap = delta + 1, D31),
    so ranges never merge across files and no ambiguous zone reaches the next file."""
    if gap < 1:
        raise ValueError("gap must be at least 1 step")
    yt, yp = [], []
    for i, (t, p) in enumerate(pairs):
        t, p = np.asarray(t).astype(np.int8), np.asarray(p).astype(np.int8)
        if t.shape != p.shape:
            raise ValueError("y_true and y_pred of a file must have the same length")
        if i:
            yt.append(np.zeros(gap, np.int8))
            yp.append(np.zeros(gap, np.int8))
        yt.append(t)
        yp.append(p)
    if not yt:
        return np.zeros(0, np.int8), np.zeros(0, np.int8)
    return np.concatenate(yt), np.concatenate(yp)
