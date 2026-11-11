"""Tests for run artifacts: written once, hash-checked on read."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.backtest.runs import (
    RunError,
    list_runs,
    read_manifest,
    read_table,
    write_run,
)

RUN_A = "20261111T120000000000Z-0123abcd"
RUN_B = "20261111T120001000000Z-89ef4567"


def tables() -> dict[str, pd.DataFrame]:
    idx = pd.bdate_range("2020-01-01", periods=4, name="date")
    daily = pd.DataFrame(
        {"position": np.array([0, 1, 1, 0], dtype=np.int8), "ret": [0.0, 0.01, -0.02, 0.0]},
        index=idx,
    )
    trades = pd.DataFrame(
        {"exit_date": [idx[3], pd.NaT], "exit_reason": ["exit", ""], "open": [False, True]}
    )
    return {"daily": daily, "trades": trades}


def test_write_and_read_round_trip(tmp_path: Path) -> None:
    manifest = {"kind": "backtest", "metrics": {"sharpe": 1.25, "calmar": math.nan},
                "tickers": ("KO", "PEP"), "when": pd.Timestamp("2020-01-01")}
    path = write_run(tmp_path / "runs", RUN_A, manifest, tables())
    assert path == tmp_path / "runs" / RUN_A
    assert sorted(p.name for p in path.iterdir()) == [
        "daily.parquet", "run.json", "trades.parquet",
    ]
    back = read_manifest(tmp_path / "runs", RUN_A)
    assert back["run_id"] == RUN_A and back["schema_version"] == 1
    assert back["metrics"] == {"sharpe": 1.25, "calmar": None}  # NaN stored as null
    assert back["tickers"] == ["KO", "PEP"]
    assert back["files"]["daily"]["rows"] == 4
    assert back["files"]["daily"]["columns"] == ["position", "ret"]
    json.loads((path / "run.json").read_text(), parse_constant=lambda n: pytest.fail(n))
    daily = read_table(tmp_path / "runs", RUN_A, "daily")
    # Parquet does not store the index's freq attribute; values and dtypes match.
    pd.testing.assert_frame_equal(daily, tables()["daily"], check_freq=False)
    assert daily["position"].dtype == np.int8
    trades = read_table(tmp_path / "runs", RUN_A, "trades")
    assert pd.isna(trades["exit_date"].iloc[1]) and trades["open"].tolist() == [False, True]
    assert not (tmp_path / "runs" / f".tmp-{RUN_A}").exists()


def test_a_run_is_never_overwritten(tmp_path: Path) -> None:
    write_run(tmp_path, RUN_A, {"kind": "backtest", "n": 1}, tables())
    with pytest.raises(RunError, match="already exists"):
        write_run(tmp_path, RUN_A, {"kind": "backtest", "n": 2}, tables())
    assert read_manifest(tmp_path, RUN_A)["n"] == 1


def test_a_changed_table_is_detected(tmp_path: Path) -> None:
    write_run(tmp_path, RUN_A, {"kind": "backtest"}, tables())
    other = tables()["daily"]
    other.iloc[1, 1] = 9.0
    other.to_parquet(tmp_path / RUN_A / "daily.parquet")
    with pytest.raises(RunError, match="does not match the hash"):
        read_table(tmp_path, RUN_A, "daily")
    read_table(tmp_path, RUN_A, "trades")  # the untouched table still reads
    (tmp_path / RUN_A / "trades.parquet").unlink()
    with pytest.raises(RunError, match="missing"):
        read_table(tmp_path, RUN_A, "trades")
    with pytest.raises(RunError, match="no table"):
        read_table(tmp_path, RUN_A, "signals")


def test_list_runs_is_sorted_and_ignores_other_folders(tmp_path: Path) -> None:
    assert list_runs(tmp_path / "nothing") == []
    write_run(tmp_path, RUN_B, {"kind": "control_batch"}, {})
    write_run(tmp_path, RUN_A, {"kind": "backtest"}, tables())
    (tmp_path / ".tmp-leftover").mkdir()
    (tmp_path / "notes").mkdir()
    assert [m["run_id"] for m in list_runs(tmp_path)] == [RUN_A, RUN_B]


def test_failed_write_leaves_nothing_behind(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        write_run(tmp_path, RUN_A, {"kind": "backtest", "bad": object()}, tables())
    assert list(tmp_path.iterdir()) == []
    write_run(tmp_path, RUN_A, {"kind": "backtest"}, tables())  # the id is still free


@pytest.mark.parametrize(
    ("run_id", "manifest", "names"),
    [
        ("../escape", {"kind": "backtest"}, ["daily"]),
        ("20261111T120000000000Z-XYZ", {"kind": "backtest"}, ["daily"]),
        (RUN_A, {"kind": "guess"}, ["daily"]),
        (RUN_A, {}, ["daily"]),
        (RUN_A, {"kind": "backtest"}, ["../daily"]),
        (RUN_A, {"kind": "backtest"}, ["Daily"]),
    ],
)
def test_invalid_arguments_raise(
    tmp_path: Path, run_id: str, manifest: dict[str, object], names: list[str]
) -> None:
    with pytest.raises(ValueError):
        write_run(tmp_path, run_id, manifest, {n: tables()["daily"] for n in names})
    assert not any(tmp_path.iterdir())


def test_damaged_manifests_are_refused(tmp_path: Path) -> None:
    with pytest.raises(RunError, match="no run"):
        read_manifest(tmp_path, RUN_A)
    write_run(tmp_path, RUN_A, {"kind": "backtest"}, {})
    path = tmp_path / RUN_A / "run.json"
    good = path.read_text()
    path.write_text("{not json")
    with pytest.raises(RunError, match="not valid JSON"):
        read_manifest(tmp_path, RUN_A)
    path.write_text(good.replace('"schema_version": 1', '"schema_version": 99'))
    with pytest.raises(RunError, match="schema version"):
        read_manifest(tmp_path, RUN_A)
    path.write_text(good.replace(RUN_A, RUN_B))
    with pytest.raises(RunError, match="another run"):
        read_manifest(tmp_path, RUN_A)
    with pytest.raises(ValueError):
        read_manifest(tmp_path, "../x")
