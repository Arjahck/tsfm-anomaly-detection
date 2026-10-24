from pathlib import Path

import pytest

from tsfm_ad import data
from tsfm_ad.config import load_config

ROOT = Path(__file__).resolve().parents[1]
HAS_DATA = (ROOT / "data" / "hai" / "hai-21.03" / "train3.csv.gz").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="HAI 21.03 is not in data/hai/hai-21.03")


@pytest.fixture(scope="session")
def cfg():
    c = load_config(ROOT / "configs" / "base.yaml")
    c["paths"] = {k: str(ROOT / v) for k, v in c["paths"].items()}
    return c


@pytest.fixture(scope="session")
def built(cfg):
    """data.build on the full 10 s config (in memory, nothing written)."""
    return data.build(cfg)
