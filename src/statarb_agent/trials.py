"""Append-only trial log.

Every analysis and every backtest configuration that is evaluated is written as
one JSON line to trials/trials.jsonl, which is committed to git. The log exists
so that the number of things tried is known: the Deflated Sharpe ratio needs
the number of trials, and a reader can see every pair that was looked at, not
only the ones that worked.

Rules:
- Lines are only ever appended. Nothing here rewrites or deletes a line.
- A refused or failed analysis is logged too, with its reason.
- Each line records what a reader needs to reproduce or distrust it: the label
  (case_study, exploratory, control or synthetic), tickers, period, snapshot
  ids, config hashes, code commit and dirty flag, whether free survivorship
  biased data was used, and whether the run touched the test period.
- When the test period is unlocked, an `unlock_event` line records the commit
  hashes of PREREGISTRATION.md and configs/study.yaml, once per distinct pair
  of hashes, before any trial that touches the test period.

The log computes nothing. Numbers in `results` come from tested code.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import pandas as pd

from statarb_agent.study import StudyConfig, unlock_evidence

SCHEMA_VERSION: Final = 1
KINDS: Final = ("pair_analysis", "basket_analysis", "backtest", "unlock_event")
LABELS: Final = ("case_study", "exploratory", "control", "synthetic")
OUTCOMES: Final = ("ok", "refused", "error")
TRIALS_PATH: Final = Path("trials") / "trials.jsonl"


class TrialLogError(RuntimeError):
    """The trial log file is damaged or holds a line this code cannot read."""


@dataclass(frozen=True)
class Trial:
    """One line of the trial log.

    Attributes:
        trial_id: Unique id: UTC timestamp plus 8 random hex characters.
        recorded_at_utc: When the line was written (ISO 8601, UTC).
        kind: One of KINDS.
        label: One of LABELS, or None for an unlock_event.
        tickers: Tickers or series names involved, in the order analysed.
        period: Name, start and asof of the window, as ISO strings.
        data_source: "yfinance", "synthetic" or "none".
        survivorship_bias: True if the data covers only tickers that still
            trade (all free real data in this project).
        snapshot_ids: Snapshot id used for each ticker.
        config_hashes: SHA-256 of each config file used.
        code_commit: Git commit of the code, or "unknown".
        code_dirty: True if tracked files had uncommitted changes.
        test_period_touched: True if any row from the test period was read.
        unlock: Commit hashes that unlocked the test period, or None if locked.
        outcome: "ok", "refused" (a data check or rule stopped it) or "error".
        reason: Why it was refused or failed, or None.
        parameters: Settings of the run that are not in a config file.
        results: Numbers produced by tested code. Non-finite floats are null.
        schema_version: Version of this layout.
    """

    trial_id: str
    recorded_at_utc: str
    kind: str
    label: str | None
    tickers: tuple[str, ...]
    period: dict[str, Any]
    data_source: str
    survivorship_bias: bool
    snapshot_ids: dict[str, str]
    config_hashes: dict[str, str]
    code_commit: str
    code_dirty: bool
    test_period_touched: bool
    unlock: dict[str, str] | None
    outcome: str
    reason: str | None
    parameters: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if self.kind == "unlock_event":
            if self.label is not None:
                raise ValueError("an unlock_event has no label")
            if self.unlock is None:
                raise ValueError("an unlock_event must record the unlock commits")
        elif self.label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}, got {self.label!r}")
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")
        if self.outcome != "ok" and not self.reason:
            raise ValueError("a refused or failed trial needs a reason")
        if self.test_period_touched and self.unlock is None:
            raise ValueError(
                "a trial that touched the test period must record the unlock commits"
            )

    def to_json(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["tickers"] = list(self.tickers)
        return json_safe(data)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Trial:
        names = {f.name for f in dataclasses.fields(cls)}
        if set(data) != names:
            raise TrialLogError(
                f"trial line has keys {sorted(set(data) ^ names)} missing or unknown"
            )
        if data["schema_version"] != SCHEMA_VERSION:
            raise TrialLogError(
                f"trial schema version {data['schema_version']!r} is not supported"
            )
        return cls(**{**data, "tickers": tuple(data["tickers"])})


def json_safe(value: Any) -> Any:
    """Copy `value` into plain JSON types; NaN and infinity become null.

    Strict JSON has no NaN. A statistic that is undefined is stored as null so
    every line parses in any language.

    Raises:
        TypeError: On a type with no JSON form (so nothing is stored by repr).
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item") and callable(value.item):  # numpy scalar
        return json_safe(value.item())
    raise TypeError(f"cannot store a {type(value).__name__} in the trial log")


def new_trial_id(now: pd.Timestamp) -> str:
    """UTC timestamp to the microsecond plus 8 random hex characters."""
    return f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(4)}"


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


class TrialLog:
    """The JSONL file of trials. Append and read only."""

    def __init__(
        self, path: Path, *, clock: Callable[[], pd.Timestamp] = utc_now
    ) -> None:
        self.path = Path(path)
        self.clock = clock

    def read(self) -> list[Trial]:
        """Every trial, oldest first. A missing file is an empty log.

        Raises:
            TrialLogError: If a line is not valid JSON, has unknown or missing
                keys, or the file does not end with a newline (a torn write).
        """
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            raise TrialLogError(
                f"{self.path} does not end with a newline; the last line is incomplete"
            )
        trials: list[Trial] = []
        for number, line in enumerate(text.splitlines(), start=1):
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TrialLogError(f"{self.path} line {number} is not JSON") from exc
            if not isinstance(data, dict):
                raise TrialLogError(f"{self.path} line {number} is not an object")
            try:
                trials.append(Trial.from_json(data))
            except (TypeError, ValueError) as exc:
                raise TrialLogError(f"{self.path} line {number}: {exc}") from exc
        return trials

    def append(self, trial: Trial) -> Trial:
        """Write one trial as one line and flush it to disk.

        The existing file is read first, so a damaged log stops new writes
        instead of growing past the damage. The line is written with a single
        os.write on a descriptor opened with O_APPEND, so it lands at the end
        of the file whole.

        Raises:
            TrialLogError: If the existing log is damaged or already holds
                this trial_id.
        """
        if any(t.trial_id == trial.trial_id for t in self.read()):
            raise TrialLogError(f"trial id {trial.trial_id} is already in the log")
        line = json.dumps(trial.to_json(), sort_keys=True, allow_nan=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return trial

    def record(
        self,
        *,
        kind: str,
        label: str | None,
        tickers: tuple[str, ...],
        period: dict[str, Any],
        data_source: str,
        survivorship_bias: bool,
        snapshot_ids: dict[str, str],
        config_hashes: dict[str, str],
        code_commit: str,
        code_dirty: bool,
        test_period_touched: bool,
        unlock: dict[str, str] | None,
        outcome: str,
        reason: str | None = None,
        parameters: dict[str, Any] | None = None,
        results: dict[str, Any] | None = None,
    ) -> Trial:
        """Build a trial with a new id and the current time, and append it."""
        now = self.clock()
        return self.append(
            Trial(
                trial_id=new_trial_id(now),
                recorded_at_utc=now.isoformat(),
                kind=kind,
                label=label,
                tickers=tuple(tickers),
                period=dict(period),
                data_source=data_source,
                survivorship_bias=survivorship_bias,
                snapshot_ids=dict(snapshot_ids),
                config_hashes=dict(config_hashes),
                code_commit=code_commit,
                code_dirty=code_dirty,
                test_period_touched=test_period_touched,
                unlock=None if unlock is None else dict(unlock),
                outcome=outcome,
                reason=reason,
                parameters=dict(parameters or {}),
                results=dict(results or {}),
            )
        )

    def count(self, *, kind: str | None = None, outcome: str | None = None) -> int:
        """Number of trials, optionally of one kind and one outcome."""
        return sum(
            1
            for t in self.read()
            if (kind is None or t.kind == kind)
            and (outcome is None or t.outcome == outcome)
        )


def unlock_record(study: StudyConfig, repo_root: Path) -> dict[str, str] | None:
    """The unlock commits as a dict for a trial, or None while locked."""
    evidence = unlock_evidence(study, repo_root)
    return None if evidence is None else dataclasses.asdict(evidence)


def record_unlock_event(
    log: TrialLog,
    study: StudyConfig,
    repo_root: Path,
    *,
    config_hashes: dict[str, str],
    code_commit: str,
    code_dirty: bool,
) -> Trial | None:
    """Log that the test period is unlocked, once per distinct pair of commits.

    Call this before any run while unlocked. Returns None while the test
    period is locked. If the log already has an unlock_event with the same
    two commit hashes, that line is returned and nothing is written.
    """
    unlock = unlock_record(study, repo_root)
    if unlock is None:
        return None
    for trial in log.read():
        if trial.kind == "unlock_event" and trial.unlock == unlock:
            return trial
    return log.record(
        kind="unlock_event",
        label=None,
        tickers=(),
        period={},
        data_source="none",
        survivorship_bias=False,
        snapshot_ids={},
        config_hashes=config_hashes,
        code_commit=code_commit,
        code_dirty=code_dirty,
        test_period_touched=False,
        unlock=unlock,
        outcome="ok",
    )
