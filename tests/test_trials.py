"""Tests for the append-only trial log."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.provenance import config_hashes, file_sha256
from statarb_agent.study import PREREGISTRATION_FILE, STUDY_CONFIG, load_study
from statarb_agent.trials import (
    Trial,
    TrialLog,
    TrialLogError,
    json_safe,
    new_trial_id,
    record_unlock_event,
    unlock_record,
)

STUDY_YAML = """
formation: {start: "2010-01-01", end: "2017-12-31"}
validation: {start: "2018-01-01", end: "2021-12-31"}
test_start: "2022-01-01"
test_period_unlocked: FLAG
"""


class Clock:
    """Returns a fixed time that advances one second per call."""

    def __init__(self) -> None:
        self.now = pd.Timestamp("2026-11-10 12:00:00", tz="UTC")

    def __call__(self) -> pd.Timestamp:
        self.now += pd.Timedelta(seconds=1)
        return self.now


def _fields(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "pair_analysis",
        "label": "case_study",
        "tickers": ("KO", "PEP"),
        "period": {"name": "formation", "start": "2010-01-01", "asof": "2018-01-01"},
        "data_source": "yfinance",
        "survivorship_bias": True,
        "snapshot_ids": {"KO": "yfinance/KO/1", "PEP": "yfinance/PEP/1"},
        "config_hashes": {"screen": "ab" * 32},
        "code_commit": "c" * 40,
        "code_dirty": False,
        "test_period_touched": False,
        "unlock": None,
        "outcome": "ok",
    }
    return {**base, **changes}


@pytest.fixture
def log(tmp_path: Path) -> TrialLog:
    return TrialLog(tmp_path / "trials" / "trials.jsonl", clock=Clock())


def test_missing_file_is_an_empty_log(log: TrialLog) -> None:
    assert log.read() == [] and log.count() == 0


def test_record_and_read_round_trip(log: TrialLog) -> None:
    first = log.record(**_fields(results={"beta": 1.5, "passed": True}))
    second = log.record(**_fields(label="exploratory", outcome="refused",
                                  reason="KO is missing 3 trading days"))
    assert log.read() == [first, second]
    assert first.trial_id != second.trial_id
    assert first.trial_id.startswith("20261110T120001000000Z-")
    assert first.recorded_at_utc == "2026-11-10T12:00:01+00:00"
    assert first.schema_version == 1 and first.results["beta"] == 1.5
    assert log.count() == 2
    assert log.count(kind="pair_analysis", outcome="refused") == 1
    assert log.count(kind="backtest") == 0


def test_each_line_is_strict_sorted_json(log: TrialLog) -> None:
    log.record(**_fields(results={"half_life": math.nan, "p": np.float64(0.25),
                                  "n": np.int64(3), "when": pd.Timestamp("2017-12-29")}))
    lines = log.path.read_text().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0], parse_constant=lambda name: pytest.fail(name))
    assert data["results"] == {"half_life": None, "p": 0.25, "n": 3,
                               "when": "2017-12-29T00:00:00"}
    assert list(data) == sorted(data)
    assert data["tickers"] == ["KO", "PEP"]


def test_append_never_changes_earlier_bytes(log: TrialLog) -> None:
    log.record(**_fields())
    before = log.path.read_bytes()
    log.record(**_fields(label="control"))
    log.record(**_fields(label="synthetic", data_source="synthetic",
                         survivorship_bias=False))
    after = log.path.read_bytes()
    assert after.startswith(before) and after.count(b"\n") == 3


def test_duplicate_id_is_refused(log: TrialLog) -> None:
    trial = log.record(**_fields())
    with pytest.raises(TrialLogError, match="already in the log"):
        log.append(trial)
    assert log.count() == 1


@pytest.mark.parametrize(
    "damage",
    ["not json\n", "[1, 2]\n", '{"trial_id": "x"}\n', '{"half": '],
)
def test_damaged_log_stops_reads_and_writes(log: TrialLog, damage: str) -> None:
    log.record(**_fields())
    good = log.path.read_text()
    log.path.write_text(good + damage)
    with pytest.raises(TrialLogError):
        log.read()
    with pytest.raises(TrialLogError):
        log.record(**_fields())
    assert log.path.read_text() == good + damage


def test_unknown_schema_version_is_refused(log: TrialLog) -> None:
    trial = log.record(**_fields())
    data = trial.to_json()
    data["schema_version"] = 99
    log.path.write_text(json.dumps(data) + "\n")
    with pytest.raises(TrialLogError, match="schema version"):
        log.read()


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "guess"},
        {"label": "famous"},
        {"label": None},
        {"outcome": "great"},
        {"outcome": "refused"},
        {"outcome": "error", "reason": ""},
        {"test_period_touched": True},
        {"kind": "unlock_event"},
        {"kind": "unlock_event", "label": None},
    ],
)
def test_invalid_trials_are_rejected(log: TrialLog, changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        log.record(**_fields(**changes))
    assert not log.path.exists()


def test_json_safe_rejects_unknown_types() -> None:
    with pytest.raises(TypeError, match="cannot store"):
        json_safe({"x": object()})
    assert json_safe({"a": (1, 2.5, None, True), "inf": math.inf}) == {
        "a": [1, 2.5, None, True], "inf": None,
    }


def test_trial_ids_sort_by_time() -> None:
    early = new_trial_id(pd.Timestamp("2026-11-10 12:00:00", tz="UTC"))
    late = new_trial_id(pd.Timestamp("2026-11-10 12:00:00.000001", tz="UTC"))
    assert early[:-9] < late[:-9] and len(early) == len("20261110T120000000000Z") + 9


def test_config_hashes(tmp_path: Path) -> None:
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("x: 1\n")
    b.write_text("x: 2\n")
    hashes = config_hashes({"b": b, "a": a})
    assert list(hashes) == ["a", "b"] and hashes["a"] != hashes["b"]
    assert hashes["a"] == file_sha256(a) and len(hashes["a"]) == 64
    # SHA-256 of the empty input, a published constant
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    assert file_sha256(empty) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


# Unlock events -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _repo(tmp_path: Path, *, unlocked: bool) -> Path:
    repo = tmp_path / "repo"
    (repo / STUDY_CONFIG).parent.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / STUDY_CONFIG).write_text(
        STUDY_YAML.replace("FLAG", "true" if unlocked else "false")
    )
    (repo / PREREGISTRATION_FILE).write_text("plan\n")
    _git(repo, "add", STUDY_CONFIG.as_posix())
    _git(repo, "commit", "-q", "-m", "config")
    _git(repo, "add", PREREGISTRATION_FILE)
    _git(repo, "commit", "-q", "-m", "plan")
    return repo


def _event(log: TrialLog, repo: Path) -> Trial | None:
    study = load_study(repo / STUDY_CONFIG)
    return record_unlock_event(
        log, study, repo, config_hashes={"study": "s"}, code_commit="c",
        code_dirty=False,
    )


def test_no_unlock_event_while_locked(tmp_path: Path, log: TrialLog) -> None:
    repo = _repo(tmp_path, unlocked=False)
    assert _event(log, repo) is None
    assert unlock_record(load_study(repo / STUDY_CONFIG), repo) is None
    assert log.count() == 0


def test_unlock_event_records_both_commits_once(tmp_path: Path, log: TrialLog) -> None:
    repo = _repo(tmp_path, unlocked=True)
    plan_commit = _git(repo, "rev-parse", "HEAD")
    config_commit = _git(repo, "rev-parse", "HEAD~1")
    event = _event(log, repo)
    assert event is not None and event.kind == "unlock_event"
    assert event.unlock == {
        "preregistration_commit": plan_commit,
        "study_config_commit": config_commit,
    }
    assert _event(log, repo) == event  # same commits: nothing new is written
    assert log.count(kind="unlock_event") == 1
    # a trial that touches the test period can now be recorded, with the commits
    trial = log.record(**_fields(test_period_touched=True, unlock=event.unlock))
    assert log.read()[-1] == trial


def test_a_new_plan_commit_is_a_new_unlock_event(tmp_path: Path, log: TrialLog) -> None:
    repo = _repo(tmp_path, unlocked=True)
    first = _event(log, repo)
    (repo / PREREGISTRATION_FILE).write_text("plan, revised\n")
    _git(repo, "add", PREREGISTRATION_FILE)
    _git(repo, "commit", "-q", "-m", "revise plan")
    second = _event(log, repo)
    assert first is not None and second is not None
    assert second.unlock != first.unlock and log.count(kind="unlock_event") == 2
