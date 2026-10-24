"""YAML configs with `base:` inheritance, run keys, the forecast hash and seeds (PLAN.md sections 6.1, 11)."""
from __future__ import annotations

import copy
import hashlib
import json
import random
from pathlib import Path
from typing import NamedTuple

import numpy as np
import yaml

SRC_DIR = Path(__file__).resolve().parent
TSFM_MODELS = ("chronos2", "timestral")    # model.name of a forecasting model; `baseline` is experiment 5
# Hashed sources per model.name (PLAN.md 6.1 (c), D65, D120): editing one changes that model's forecast hashes only.
MODEL_SOURCES = {
    "chronos2": ("forecast.py", "context.py", "model_chronos2.py"),
    "timestral": ("forecast.py", "context.py", "mps_shim.py"),
    "baseline": ("baselines.py",),
}
TIMESTRAL_FLAGS = ("symmetric_averaging", "clip_nonnegative")   # Timestral-only forecast flags (PLAN.md 2.1, D14)
VARIANT_KINDS = ("rolling", "ff", "frozen", "dual", "cf-onset")


class RunKey(NamedTuple):
    dataset: str
    model: str
    setup: str
    variant: str

    def __str__(self) -> str:
        return "/".join(self)


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path) -> dict:
    """Load a YAML config. `base: <file>` (relative to this file's directory) is deep-merged first; lists replace."""
    path = Path(path)
    cfg = yaml.safe_load(path.read_text()) or {}
    base = cfg.pop("base", None)
    if base:
        cfg = _deep_merge(load_config(path.parent / base), cfg)
    cfg["_path"] = str(path)
    return cfg


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import torch  # lazy: config is imported by light modules too

    torch.manual_seed(seed)


def steps(cfg: dict, seconds: int) -> int:
    """Convert seconds to steps at the config's resolution; the value must be a whole number of steps."""
    res = cfg["dataset"]["resolution_s"]
    if seconds % res:
        raise ValueError(f"{seconds} s is not a multiple of the {res} s resolution")
    return seconds // res


def with_variant(cfg: dict, kind: str | None) -> dict:
    """A copy of cfg whose variant kind is `kind` (None keeps cfg as is)."""
    if kind is None or kind == cfg["variant"]["kind"]:
        return cfg
    if kind not in VARIANT_KINDS:
        raise ValueError(f"unknown variant kind {kind!r}; expected one of {VARIANT_KINDS}")
    out = copy.deepcopy(cfg)
    out["variant"]["kind"] = kind
    return out


def selection_csv(cfg: dict) -> Path:
    return Path(cfg["paths"]["results"]) / "selection.csv"


def resolve_setup(cfg: dict) -> str:
    setup = cfg["setup"]
    if setup == "selected":
        from tsfm_ad import selection  # only needed for `setup: selected`

        return selection.selected(cfg.get("selection_stage", "base"), selection_csv(cfg))["setup"]
    return setup


def resolve_selected(cfg: dict) -> dict:
    """A copy of cfg with `setup: selected` and `variant.kind: selected` replaced by the pick of
    `selection_stage` in <results>/selection.csv (D41). The config file itself is never edited."""
    kind_sel = cfg["variant"]["kind"] == "selected"
    if cfg["setup"] != "selected" and not kind_sel:
        return cfg
    from tsfm_ad import selection

    stage = cfg.get("selection_stage", "base")
    if kind_sel and stage != "best":
        raise ValueError("variant.kind: selected needs selection_stage: best")
    pick = selection.selected(stage, selection_csv(cfg))
    selection.check_pick(pick, cfg)                 # never a pick made on forecasts that are no longer current
    out = copy.deepcopy(cfg)
    if cfg["setup"] == "selected":
        out["setup"] = pick["setup"]
    if kind_sel:
        out["variant"]["kind"] = pick["kind"]
    return out


def model_id(cfg: dict) -> str:
    """The model without the device: `chronos2-<rev7>`, `timestral-<size>-<rev7>` or `baseline`."""
    m = cfg["model"]
    if m["name"] == "baseline":
        return "baseline"
    if m["name"] == "chronos2":   # `tag` names a second checkpoint, e.g. chronos2-small-ddec013 (D136)
        tag = m["chronos2"].get("tag")
        return f"chronos2-{tag + '-' if tag else ''}{m['chronos2']['revision'][:7]}"
    if m["name"] == "timestral":
        return f"timestral-{m['size']}-{m['revisions'][m['size']][:7]}"
    raise ValueError(f"unknown model.name {m['name']!r}; expected one of {TSFM_MODELS} or baseline")


def model_tag(cfg: dict) -> str:
    """The model part of the run key: `<model_id>-<device>`, or `baseline`."""
    mid = model_id(cfg)
    return mid if mid == "baseline" else f"{mid}-{cfg['model']['device']}"


def model_params(cfg: dict) -> int:
    """Parameter count of the configured model (size_latency.csv)."""
    m = cfg["model"]
    return m["chronos2"]["params"] if m["name"] == "chronos2" else m["params"][m["size"]]


def variant_name(cfg: dict) -> str:
    v = cfg["variant"]
    kind = v["kind"]
    if kind == "rolling":
        name = "prepend" if cfg["forecast"]["warmup"] == "prepend" else "rolling"
    elif kind == "ff":
        name = "ff-interp-block"
        max_d = v["ff"].get("max_duration")
        if max_d:
            name += f"-max{max_d}" + ("-testinf" if max_d == 60 else "")
    elif kind in VARIANT_KINDS:
        name = kind
    else:
        raise ValueError(f"unknown variant kind {kind!r}")
    if cfg["forecast"]["H"] != 30:              # D138: a horizon other than the default 30 steps names itself
        name += f"-h{cfg['forecast']['H']}"
    if cfg["dataset"]["resolution_s"] == 1 or cfg["forecast"]["cap"] != cfg["model"]["max_context"]:
        name += f"-c{cfg['forecast']['cap']}"      # D137: a 10 s run below the model maximum names its cap too
    return name


def run_key(cfg: dict) -> RunKey:
    return RunKey(cfg["dataset"]["key"], model_tag(cfg), resolve_setup(cfg), variant_name(cfg))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepared_digest(cfg: dict) -> str:
    """Digest of every prepared array (segments, norm stats, roles, attacks), written by `prepare`."""
    path = Path(cfg["paths"]["cache"]) / cfg["dataset"]["key"] / "prepared" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run `tsfm-ad prepare` first")
    return json.loads(path.read_text())["digest"]


def forecast_settings(cfg: dict) -> dict:
    """The settings that change a forecast (PLAN.md 6.1 (a)). Score and metric settings are left out on purpose."""
    kind = cfg["variant"]["kind"]
    setup = resolve_setup(cfg)
    m = cfg["model"]
    s = {
        "dataset": cfg["dataset"],
        "channels": {"rules": cfg["channels"]["rules"], "setup": cfg["channels"]["setups"].get(setup)},
        "setup": setup,
        "variant": variant_name(cfg),
        "kind": kind,
        "forecast": cfg["forecast"],
    }
    if m["name"] == "baseline":
        s["model"] = "baseline"
        s["baselines"] = cfg.get("baselines")
    elif m["name"] == "chronos2":   # Chronos-2 has no Timestral flags (PLAN.md 14): they are not in its hash
        c = m["chronos2"]
        s["forecast"] = {k: v for k, v in cfg["forecast"].items() if k not in TIMESTRAL_FLAGS}
        s["model"] = {"name": "chronos2", "repo": c["repo"], "revision": c["revision"], "package": c["package"],
                      "dtype": c.get("dtype", "float32"), "device": m["device"], "max_context": m["max_context"],
                      "cpu_threads": m.get("cpu_threads", 4)}
    elif m["name"] == "timestral":
        s["model"] = {"repo": m["repo_prefix"] + m["size"], "revision": m["revisions"][m["size"]],
                      "timestral_commit": m["timestral_commit"], "device": m["device"],
                      "max_context": m["max_context"], "cpu_threads": m.get("cpu_threads", 4)}   # D115
    else:
        raise ValueError(f"unknown model.name {m['name']!r}")
    if kind == "ff":
        s["ff"] = cfg["variant"]["ff"]
    if kind == "cf-onset":
        s["N_onset_s"] = cfg["metrics"]["N_onset_s"]
    return s


def model_sources(cfg: dict) -> tuple[str, ...]:
    """MODEL_SOURCES of model.name, plus the module named by `model.chronos2.adapter` (D136: chronos-2-small), so
    that adapter is hashed for its own model only."""
    m = cfg["model"]
    adapter = m.get("chronos2", {}).get("adapter") if m["name"] == "chronos2" else None
    return MODEL_SOURCES[m["name"]] + ((f"{adapter}.py",) if adapter else ())


def forecast_hash(cfg: dict, extra=None, sources=None) -> str:
    """sha256 of (a) forecast settings, (b) the prepared-data digest, (c) the forecasting source files, (d) `extra`.

    `sources` are file names in src/tsfm_ad/ (or paths); by default `MODEL_SOURCES[model.name]` (forecast.py,
    context.py and model_chronos2.py or mps_shim.py; baselines.py for `baseline`). A listed file that does not exist
    raises FileNotFoundError.
    `extra` is any JSON-serialisable value, e.g. the FF thresholds hash. The dual variant has no inference: its hash
    is sha256 of the rolling and frozen hashes.
    """
    if cfg["variant"]["kind"] == "dual":
        parts = [forecast_hash(with_variant(cfg, k), sources=sources) for k in ("rolling", "frozen")]
        return hashlib.sha256("".join(parts).encode()).hexdigest()
    if sources is None:
        sources = model_sources(cfg)
    src = {}
    for name in sources:
        p = Path(name) if Path(name).is_absolute() else SRC_DIR / name
        if not p.exists():
            raise FileNotFoundError(f"forecast source {p} does not exist")
        src[p.name] = _sha256_file(p)
    payload = {"settings": forecast_settings(cfg), "prepared": prepared_digest(cfg), "sources": src, "extra": extra}
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()
