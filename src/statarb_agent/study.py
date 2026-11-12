"""Study periods and the test-period lock.

The brief splits the data into formation (2010 to 2017), validation (2018 to
2021) and test (2022 onward). The test period may be used once, only after
PREREGISTRATION.md is committed. Until then nothing in the library may read or
compute on dates from TEST_START onward.

TEST_START is a constant in code, not a config value, so it cannot be moved by
editing a YAML file; load_study refuses a config that disagrees with it.

The test period is unlocked only when all of these hold:
- the StudyConfig passed in sets `test_period_unlocked: true`;
- configs/study.yaml in the repository is in the HEAD commit, has no staged or
  unstaged changes, and sets `test_period_unlocked: true`;
- PREREGISTRATION.md is in the HEAD commit and has no staged or unstaged changes.
unlock_evidence returns the commit hashes of both files, so every unlock event
can be logged with them.

Limits: this protects the library paths that call it (the data sources and the
CLI). It cannot stop a notebook that reads a Parquet file directly.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import yaml

TEST_START: Final = pd.Timestamp("2022-01-01")
PREREGISTRATION_FILE: Final = "PREREGISTRATION.md"
STUDY_CONFIG: Final = Path("configs") / "study.yaml"

_KEYS: Final = {"formation", "validation", "test_start", "test_period_unlocked"}
_PERIOD_KEYS: Final = {"start", "end"}


class LockedPeriodError(PermissionError):
    """Raised when code asks for dates in the locked test period."""


@dataclass(frozen=True)
class Period:
    """A study period with an inclusive end date.

    Attributes:
        start: First date of the period.
        end: Last date of the period (inclusive).
    """

    start: pd.Timestamp
    end: pd.Timestamp

    @property
    def asof(self) -> pd.Timestamp:
        """As-of date that selects every row up to and including `end`."""
        return self.end + pd.Timedelta(days=1)


@dataclass(frozen=True)
class StudyConfig:
    """Contents of configs/study.yaml, validated."""

    formation: Period
    validation: Period
    test_start: pd.Timestamp
    test_period_unlocked: bool


def to_date(value: Any) -> pd.Timestamp:
    """Convert a date-like value to a timezone-naive Timestamp.

    Accepts str, datetime.date, datetime.datetime, numpy.datetime64 and
    pandas.Timestamp. Time of day is kept, so "2022-01-01 09:30" stays after
    TEST_START.

    Raises:
        TypeError: If the value is timezone-aware or not date-like. Session
            dates in this project are timezone-naive.
        ValueError: If the value is NaT or cannot be parsed.
    """
    if not isinstance(value, (str, dt.date, np.datetime64, pd.Timestamp)):
        raise TypeError(f"expected a date, got {type(value).__name__}")
    ts = pd.Timestamp(value)
    if ts is pd.NaT:
        raise ValueError("date must be valid, got NaT")
    if ts.tzinfo is not None:
        raise TypeError(f"dates must be timezone-naive, got {ts}")
    return ts


def _parse_period(raw: Any, name: str) -> Period:
    if not isinstance(raw, dict) or set(raw) != _PERIOD_KEYS:
        raise ValueError(f"{name} must have exactly the keys start and end")
    period = Period(start=to_date(raw["start"]), end=to_date(raw["end"]))
    if period.start > period.end:
        raise ValueError(f"{name} starts after it ends")
    return period


def load_study(path: Path) -> StudyConfig:
    """Read and validate a study config.

    Raises:
        ValueError: On unknown or missing keys, unparseable dates, periods out
            of order or overlapping, a test_start that differs from
            TEST_START, or a test_period_unlocked that is not a YAML boolean.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ValueError(f"{path} must have exactly the keys {sorted(_KEYS)}")
    formation = _parse_period(raw["formation"], "formation")
    validation = _parse_period(raw["validation"], "validation")
    test_start = to_date(raw["test_start"])
    if test_start != TEST_START:
        raise ValueError(
            f"test_start in {path} is {test_start.date()}, but the test period is "
            f"fixed in code at {TEST_START.date()}"
        )
    if not formation.end < validation.start or not validation.end < test_start:
        raise ValueError("periods must be in order: formation, validation, test")
    unlocked = raw["test_period_unlocked"]
    if type(unlocked) is not bool:
        raise ValueError("test_period_unlocked must be true or false")
    return StudyConfig(formation, validation, test_start, unlocked)


# Environment variables that tell git to use another repository, index or
# object store than the one in the folder it is run in.
_GIT_REDIRECTS: Final = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run git in repo_root and return its raw output.

    Replace references are ignored and the variables that redirect git to
    another repository are removed, so the answer is about this folder's own
    committed objects.
    """
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REDIRECTS}
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo_root), *args],
        capture_output=True,
        check=False,
        env=env,
    )


def committed_clean_commit(repo_root: Path, relpath: str) -> str | None:
    """Hash of the last commit that changed `relpath`, if it is committed and clean.

    `relpath` is relative to repo_root, with "/" separators. Returns None unless
    all of these hold:
    - the file exists, is not empty and is in HEAD;
    - `git status` reports no staged or unstaged change for it;
    - the bytes of the file on disk, read by Python, are exactly the bytes of
      the copy in HEAD (`git cat-file blob HEAD:path`).

    The third check is the one that counts. It does not rely on git's view of
    the working tree, which can be made blind to an edit: by an index flag
    (`git update-index --skip-worktree` or `--assume-unchanged`), or by a clean
    filter that rewrites the file whenever git reads it. Git is only asked for
    the committed bytes; the comparison is done here.

    A consequence: if git is set to convert line endings on checkout, the file
    on disk differs from the committed bytes and this returns None. The lock
    then stays closed, which is the safe side.

    Limits: this cannot protect against a different program named `git` placed
    earlier on PATH, or against someone editing this module. The lock guards
    against accidents and casual shortcuts, not against a determined owner of
    the machine. Any git failure (not a repository, git missing) gives None.
    """
    path = Path(repo_root) / relpath
    try:
        if not path.is_file() or path.is_symlink():
            return None
        on_disk = path.read_bytes()
        in_head = _git(repo_root, "cat-file", "blob", f"HEAD:{relpath}")
        status = _git(repo_root, "status", "--porcelain", "--", relpath)
        last = _git(repo_root, "log", "-1", "--format=%H", "--", relpath)
    except OSError:
        return None
    if not on_disk:
        return None
    if in_head.returncode != 0 or status.returncode != 0 or status.stdout.strip():
        return None
    if in_head.stdout != on_disk:
        return None
    commit = last.stdout.decode("ascii", errors="replace").strip()
    return commit if last.returncode == 0 and commit else None


def preregistration_commit(repo_root: Path) -> str | None:
    """Hash of the last commit that changed PREREGISTRATION.md, if committed and clean.

    The file must also hold some text: a file that is empty or only whitespace
    is not a pre-registration.
    """
    commit = committed_clean_commit(repo_root, PREREGISTRATION_FILE)
    if commit is None:
        return None
    try:
        text = (Path(repo_root) / PREREGISTRATION_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return commit if text.strip() else None


def study_config_commit(repo_root: Path) -> str | None:
    """Hash of the last commit that changed configs/study.yaml, if it unlocks.

    Returns None unless the file is committed and clean (as for
    PREREGISTRATION.md), is a valid study config, and sets
    `test_period_unlocked: true`. committed_clean_commit has compared the bytes
    on disk with the bytes in HEAD itself, so reading the file from disk reads
    the committed flag.
    """
    commit = committed_clean_commit(repo_root, STUDY_CONFIG.as_posix())
    if commit is None:
        return None
    try:
        committed = load_study(Path(repo_root) / STUDY_CONFIG)
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return None
    return commit if committed.test_period_unlocked else None


@dataclass(frozen=True)
class UnlockEvidence:
    """Why the test period is unlocked: the commits of the two files that unlock it.

    Attributes:
        preregistration_commit: Last commit that changed PREREGISTRATION.md.
        study_config_commit: Last commit that changed configs/study.yaml.
    """

    preregistration_commit: str
    study_config_commit: str


def unlock_evidence(study: StudyConfig, repo_root: Path) -> UnlockEvidence | None:
    """The commit hashes that unlock the test period, or None while it is locked."""
    if not study.test_period_unlocked:
        return None
    config = study_config_commit(repo_root)
    prereg = preregistration_commit(repo_root)
    if config is None or prereg is None:
        return None
    return UnlockEvidence(preregistration_commit=prereg, study_config_commit=config)


def is_test_period_unlocked(study: StudyConfig, repo_root: Path) -> bool:
    """True only if unlock_evidence finds both files committed and the flag set."""
    return unlock_evidence(study, repo_root) is not None


def _locked_message(what: str) -> str:
    return (
        f"Refused: {what} is in the test period (from {TEST_START.date()}), which is "
        f"locked until {PREREGISTRATION_FILE} is committed and {STUDY_CONFIG} is "
        "committed with test_period_unlocked: true, both with no uncommitted changes."
    )


def require_before_test_period(
    asof: Any, study: StudyConfig, repo_root: Path
) -> pd.Timestamp:
    """Return `asof` as a Timestamp, or refuse if it reaches into the test period.

    An as-of date of exactly TEST_START is allowed: estimators read rows
    strictly before asof, so it reads up to 2021-12-31.

    Raises:
        LockedPeriodError: If asof is after TEST_START and the test period is
            locked.
        TypeError, ValueError: As for to_date.
    """
    ts = to_date(asof)
    if ts > TEST_START and not is_test_period_unlocked(study, repo_root):
        raise LockedPeriodError(_locked_message(f"asof {ts}"))
    return ts


def clip_end_to_open_period(
    end: Any, study: StudyConfig, repo_root: Path
) -> pd.Timestamp:
    """Clip an exclusive download end date so no test-period row is requested.

    While locked, returns min(end, TEST_START); with an exclusive end the last
    row requested is then 2021-12-31. Unlocked, returns end unchanged.
    """
    ts = to_date(end)
    if is_test_period_unlocked(study, repo_root):
        return ts
    return min(ts, TEST_START)


def drop_locked_rows[T: (pd.Series, pd.DataFrame)](
    obj: T, study: StudyConfig, repo_root: Path
) -> T:
    """Drop rows dated on or after TEST_START while the test period is locked.

    This guards data that already contains test-period rows, for example a
    snapshot downloaded before the lock existed.

    Raises:
        TypeError: If the index is not a timezone-naive DatetimeIndex.
    """
    index = obj.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None:
        raise TypeError("index must be a timezone-naive DatetimeIndex")
    if is_test_period_unlocked(study, repo_root):
        return obj.copy()
    return obj.loc[index < TEST_START].copy()


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) to the folder holding pyproject.toml."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    raise FileNotFoundError(f"no pyproject.toml above {here}")
