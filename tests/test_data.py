"""Reading, downsampling, labels, roles, the attack PDF join and the offset strata (PLAN.md 3-4, D3-D6, D47, D56)."""
import gzip
from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from conftest import needs_data
from tsfm_ad import data, tables

# research/hai_data.md section 3.2
TRIP = ["A201", "A207", "A217", "A304", "A305", "A307", "A501", "A507", "A511"]
PCV02D = ["A101", "A202", "A302", "A402", "A512"]
STEP = {"P1_B2004", "P1_B3004", "P1_B3005", "P1_B4002", "P4_HT_PS", "P4_ST_PS"}
ACTUATOR = {"P1_FCV01D", "P1_FCV02D", "P1_FCV03D", "P1_LCV01D", "P1_PCV01D", "P3_LCP01D", "P3_LCV01D"}
T0 = datetime(2020, 7, 7, 15, 0, 0)


def _hand_frame(n=20):
    """n seconds: `cont` = 0..n-1, `stp` steps 1 -> 2 at second 7 and 2 -> 3 at second 15, `const` constant."""
    stp = np.where(np.arange(n) < 7, 1.0, np.where(np.arange(n) < 15, 2.0, 3.0))
    att = np.zeros(n, np.int8)
    att[13] = 1  # one attack second in the second bin
    return pl.DataFrame({
        "time": [T0 + timedelta(seconds=i) for i in range(n)],
        "cont": np.arange(n, dtype=float), "stp": stp, "const": np.full(n, 5.0),
        "attack": att, "attack_P1": att, "attack_P2": np.zeros(n, np.int8), "attack_P3": np.zeros(n, np.int8),
    }, schema_overrides={"time": pl.Datetime("us")})


ROLES = pl.DataFrame({"channel": ["cont", "stp", "const"], "role": ["continuous", "step", "dropped"]})


def test_read_drops_last_row_and_casts(tmp_path):
    lines = ["time,P1_A,P1_BD,attack,attack_P1,attack_P2,attack_P3"]
    for i in range(5):
        t = (T0 + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{t},{i},12,0,0,0,0")  # integer-looking values must still become Float64
    path = tmp_path / "x.csv.gz"
    with gzip.open(path, "wt") as f:
        f.write("\n".join(lines) + "\n")
    df = data.read_hai_file(path)
    assert df.height == 4
    assert df["time"][-1] == T0 + timedelta(seconds=3)
    assert df.schema["P1_A"] == pl.Float64 and df.schema["P1_BD"] == pl.Float64
    assert all(df.schema[c] == pl.Int8 for c in data.LABELS)
    assert isinstance(df.schema["time"], pl.Datetime)


def test_downsample_10s_mean_last_max():
    out = data.downsample(_hand_frame(), ROLES, 10)
    assert out.columns == ["time", "cont", "stp", *data.LABELS]  # dropped tag gone
    assert out["time"].to_list() == [T0, T0 + timedelta(seconds=10)]
    assert out["cont"].to_list() == [4.5, 14.5]          # mean
    assert out["stp"].to_list() == [2.0, 3.0]            # last value in the bin
    assert out["attack"].to_list() == [0, 1]             # max keeps the single attack second
    assert out["attack_P1"].to_list() == [0, 1]


def test_label_max_keeps_one_second_attack_at_bin_edges():
    for sec in (0, 9, 10, 19):
        df = _hand_frame().with_columns(attack=pl.Series(np.eye(20, dtype=np.int8)[sec]))
        out = data.downsample(df, ROLES, 10)
        assert out["attack"].to_list() == [int(sec < 10), int(sec >= 10)]


def test_downsample_1s_only_drops_and_partial_bin_raises():
    out = data.downsample(_hand_frame(), ROLES, 1)
    assert out.height == 20 and "const" not in out.columns
    with pytest.raises(ValueError):
        data.downsample(_hand_frame(15), ROLES, 10)


def test_attack_events_runs():
    y = np.array([0, 1, 1, 0, 0, 1, 0, 1])
    ev = data.attack_events(y, np.arange(8), "f")
    assert ev["start_idx"].to_list() == [1, 5, 7]
    assert ev["end_idx"].to_list() == [2, 5, 7]
    assert ev["event"].to_list() == [1, 2, 3]


def test_window_stats_hand_values():
    # W=150, H=30: origins 150, 180, ...; attack 211..230 lies in window [210, 240) -> 1 window, 0 post-onset steps
    assert tables.window_stats(211, 230, 150, 30) == (1, 0)
    # attack 200..245: windows from 180 and 210 and 240; steps 210..245 have origin > 200
    assert tables.window_stats(200, 245, 150, 30) == (3, 36)


@needs_data
def test_float64_in_every_file(built):
    for name, df in built["raw"].items():
        tags = data.tag_columns(df)
        assert len(tags) == 79, name
        assert all(df.schema[c] == pl.Float64 for c in tags), name
        assert all(df.schema[c] == pl.Int8 for c in data.LABELS), name


@needs_data
def test_roles_use_fit_and_calib_rows_only(cfg, built):
    rows = data.roles_rows(cfg, built["raw"])
    assert set(rows["file"].unique()) == {"train1", "train2", "train3"}
    t1 = rows.filter(pl.col("file") == "train1")["time"]
    assert t1.min() == datetime(2020, 7, 11) and t1.max() == datetime(2020, 7, 12, 23, 59, 59)
    assert rows.height == 172_800 + 226_800 + 478_800


@needs_data
def test_role_counts_and_sets(built):
    r = built["roles"]
    counts = {k: r.filter(pl.col("role") == k).height for k in data.ROLES}
    assert counts == {"dropped": 22, "step": 6, "actuator": 7, "continuous": 44}
    assert set(r.filter(pl.col("role") == "step")["channel"]) == STEP
    assert set(r.filter(pl.col("role") == "actuator")["channel"]) == ACTUATOR


@needs_data
def test_channel_sets(cfg, built):
    sets = data.channel_sets(cfg, built["roles"])
    assert {k: len(sets[k]) for k in ("uni51", "uni57", "mvlit34", "mvacttgt41")} == \
        {"uni51": 51, "uni57": 57, "mvlit34": 34, "mvacttgt41": 41}
    assert len(sets["mvlit34-noPCV02Z"]) == 33 and "P1_PCV02Z" not in sets["uni51-noPCV02Z"]
    g = {x.name: (len(x.targets), len(x.covariates)) for x in data.setup_groups(cfg, "mv-lit", built["roles"])}
    assert g == {"P1": (21, 9), "P2": (10, 0), "P3": (3, 2)}
    g = {x.name: (len(x.targets), len(x.covariates)) for x in data.setup_groups(cfg, "mv-acttgt", built["roles"])}
    assert g == {"P1": (26, 4), "P2": (10, 0), "P3": (5, 0)}


@needs_data
def test_attack_pdf_join_gives_50_in_order(built):
    ids = built["events"]["attack_id"].to_list()
    expected = [f"A{f}{i:02d}" for f, n in ((1, 5), (2, 20), (3, 8), (4, 5), (5, 12)) for i in range(1, n + 1)]
    assert ids == expected
    assert built["attacks"]["attack_id"].to_list() == expected
    assert int(built["events"]["duration_s"].sum()) == 8947


@needs_data
def test_strata_match_research_notes(built):
    a = built["events"]
    assert a.filter(pl.col("stratum") == "trip")["attack_id"].to_list() == TRIP
    assert a.filter(pl.col("stratum") == "pcv02d")["attack_id"].to_list() == PCV02D
    assert a.filter(pl.col("stratum") == "other").height == 50 - len(TRIP) - len(PCV02D)


@needs_data
def test_10s_attack_steps_and_windows(cfg, built):
    assert int(built["attacks"]["n_steps"].sum()) == 934
    a = tables.attacks_csv(cfg, built)
    assert int(a["post_onset_steps_10s"].sum()) == 232 and int((a["n_windows_10s"] == 1).sum()) == 33
    assert int(a["post_onset_steps_1s"].sum()) == 7698
    assert sorted(a.filter(pl.col("interior_empty_10s"))["attack_id"]) == ["A203", "A211", "A508"]
    assert int(a["interior_eq_10s"].sum()) == 37
