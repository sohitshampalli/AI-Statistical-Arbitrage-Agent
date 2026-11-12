"""Tests for study periods and the test-period lock.

Each git scenario builds a throwaway repository in tmp_path, with global and
system git config disabled so the user's settings cannot change the outcome.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.study import (
    PREREGISTRATION_FILE,
    STUDY_CONFIG,
    TEST_START,
    LockedPeriodError,
    StudyConfig,
    UnlockEvidence,
    clip_end_to_open_period,
    drop_locked_rows,
    find_repo_root,
    is_test_period_unlocked,
    load_study,
    preregistration_commit,
    require_before_test_period,
    study_config_commit,
    to_date,
    unlock_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID_YAML = """
formation: {start: "2010-01-01", end: "2017-12-31"}
validation: {start: "2018-01-01", end: "2021-12-31"}
test_start: "2022-01-01"
test_period_unlocked: FLAG
"""


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
    )


def _study(tmp_path: Path, flag: bool) -> StudyConfig:
    path = tmp_path / "study.yaml"
    path.write_text(VALID_YAML.replace("FLAG", "true" if flag else "false"))
    return load_study(path)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("x\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _commit_prereg(repo: Path) -> None:
    (repo / PREREGISTRATION_FILE).write_text("plan\n")
    _git(repo, "add", PREREGISTRATION_FILE)
    _git(repo, "commit", "-q", "-m", "prereg")


def _write_config(repo: Path, flag: bool) -> None:
    path = repo / STUDY_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(VALID_YAML.replace("FLAG", "true" if flag else "false"))


def _commit_config(repo: Path, flag: bool) -> None:
    _write_config(repo, flag)
    _git(repo, "add", STUDY_CONFIG.as_posix())
    _git(repo, "commit", "-q", "-m", f"study config, flag {flag}")


def _unlock(repo: Path) -> None:
    """Every unlock condition: config committed with the flag, plan committed."""
    _commit_config(repo, True)
    _commit_prereg(repo)


# Config ------------------------------------------------------------------


def test_project_config_loads_and_is_locked() -> None:
    study = load_study(REPO_ROOT / "configs" / "study.yaml")
    assert study.formation.start == pd.Timestamp("2010-01-01")
    assert study.formation.end == pd.Timestamp("2017-12-31")
    assert study.formation.asof == pd.Timestamp("2018-01-01")
    assert study.validation.start == pd.Timestamp("2018-01-01")
    assert study.validation.end == pd.Timestamp("2021-12-31")
    assert study.test_start == TEST_START == pd.Timestamp("2022-01-01")
    assert study.test_period_unlocked is False
    assert not (REPO_ROOT / PREREGISTRATION_FILE).exists()
    assert not is_test_period_unlocked(study, REPO_ROOT)


def test_config_cannot_move_test_start(tmp_path: Path) -> None:
    path = tmp_path / "study.yaml"
    moved = VALID_YAML.replace("FLAG", "false").replace(
        'test_start: "2022-01-01"', 'test_start: "2030-01-01"'
    )
    path.write_text(moved)
    with pytest.raises(ValueError, match="fixed in code"):
        load_study(path)


@pytest.mark.parametrize(
    "edit",
    [
        ("test_period_unlocked: FLAG", 'test_period_unlocked: "true"'),  # a string
        ("test_period_unlocked: FLAG", "test_period_unlocked: 1"),  # an int
        ("test_period_unlocked: FLAG", "test_period_unlocked: FLAG\nextra: 1"),
        ('test_start: "2022-01-01"\n', ""),  # missing key
        ('end: "2017-12-31"', 'end: "2018-06-30"'),  # formation overlaps validation
        ('start: "2010-01-01"', 'start: "2010-01-01", middle: "2012-01-01"'),
        ('end: "2021-12-31"', 'end: "not a date"'),
    ],
)
def test_bad_config_raises(tmp_path: Path, edit: tuple[str, str]) -> None:
    path = tmp_path / "study.yaml"
    path.write_text(VALID_YAML.replace(*edit).replace("FLAG", "false"))
    with pytest.raises(ValueError):
        load_study(path)


def test_unquoted_yaml_dates_are_accepted(tmp_path: Path) -> None:
    path = tmp_path / "study.yaml"
    path.write_text(VALID_YAML.replace('"', "").replace("FLAG", "false"))
    assert load_study(path).test_start == TEST_START


# Unlock conditions -------------------------------------------------------


def test_flag_without_file_stays_locked(tmp_path: Path, repo: Path) -> None:
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_untracked_file_stays_locked(tmp_path: Path, repo: Path) -> None:
    (repo / PREREGISTRATION_FILE).write_text("plan\n")
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_staged_but_uncommitted_file_stays_locked(tmp_path: Path, repo: Path) -> None:
    (repo / PREREGISTRATION_FILE).write_text("plan\n")
    _git(repo, "add", PREREGISTRATION_FILE)
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_modified_after_commit_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    (repo / PREREGISTRATION_FILE).write_text("plan, edited after the commit\n")
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_committed_file_without_flag_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    assert preregistration_commit(repo) is not None
    assert not is_test_period_unlocked(_study(tmp_path, False), repo)


def test_not_a_git_repository_stays_locked(tmp_path: Path) -> None:
    folder = tmp_path / "plain"
    folder.mkdir()
    (folder / PREREGISTRATION_FILE).write_text("plan\n")
    assert preregistration_commit(folder) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), folder)


def test_flag_and_committed_file_unlock(tmp_path: Path, repo: Path) -> None:
    _unlock(repo)
    commit = preregistration_commit(repo)
    assert commit is not None and len(commit) == 40
    study = _study(tmp_path, True)
    assert is_test_period_unlocked(study, repo)
    assert require_before_test_period("2023-06-30", study, repo) == pd.Timestamp(
        "2023-06-30"
    )


# The committed study config -----------------------------------------------


def test_committed_plan_without_committed_config_stays_locked(
    tmp_path: Path, repo: Path
) -> None:
    """The flag in a config outside the repository is not enough."""
    _commit_prereg(repo)
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_untracked_config_flag_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    _write_config(repo, True)
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_uncommitted_flag_stays_locked(tmp_path: Path, repo: Path) -> None:
    """Committed as false, then set to true on disk without a commit."""
    _commit_prereg(repo)
    _commit_config(repo, False)
    _write_config(repo, True)
    assert study_config_commit(repo) is None
    assert unlock_evidence(_study(tmp_path, True), repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_staged_flag_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    _commit_config(repo, False)
    _write_config(repo, True)
    _git(repo, "add", STUDY_CONFIG.as_posix())
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_committed_false_flag_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    _commit_config(repo, False)
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_config_edited_after_unlock_relocks(tmp_path: Path, repo: Path) -> None:
    _unlock(repo)
    assert is_test_period_unlocked(_study(tmp_path, True), repo)
    path = repo / STUDY_CONFIG
    path.write_text(path.read_text() + "# edited\n")
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_invalid_committed_config_stays_locked(tmp_path: Path, repo: Path) -> None:
    _commit_prereg(repo)
    path = repo / STUDY_CONFIG
    path.parent.mkdir(parents=True)
    path.write_text(VALID_YAML.replace("FLAG", "true").replace("2022-01-01", "2023-01-01"))
    _git(repo, "add", STUDY_CONFIG.as_posix())
    _git(repo, "commit", "-q", "-m", "bad config")
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_locked_study_object_stays_locked_even_if_repo_unlocks(
    tmp_path: Path, repo: Path
) -> None:
    _unlock(repo)
    assert unlock_evidence(_study(tmp_path, False), repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, False), repo)


def test_unlock_evidence_records_both_commits(tmp_path: Path, repo: Path) -> None:
    _commit_config(repo, True)
    config_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
        check=True,
    ).stdout.strip()
    _commit_prereg(repo)
    prereg_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
        check=True,
    ).stdout.strip()
    evidence = unlock_evidence(_study(tmp_path, True), repo)
    assert evidence == UnlockEvidence(
        preregistration_commit=prereg_head, study_config_commit=config_head
    )
    assert config_head != prereg_head


def test_locked_message_names_both_files(tmp_path: Path, repo: Path) -> None:
    with pytest.raises(LockedPeriodError) as info:
        require_before_test_period("2022-06-01", _study(tmp_path, True), repo)
    message = str(info.value)
    assert PREREGISTRATION_FILE in message and str(STUDY_CONFIG) in message
    assert "no uncommitted changes" in message


# Git index flags and empty files (independent review, 2026-11-11) ---------


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_flag_hidden_from_git_status_stays_locked(
    tmp_path: Path, repo: Path, flag: str
) -> None:
    """git can be told to ignore a changed file; the lock must not be fooled.

    HEAD holds the flag as false. The file is marked with a git index flag and
    then edited to true on disk. `git status` reports nothing, so a check that
    trusted it would unlock.
    """
    _commit_prereg(repo)
    _commit_config(repo, False)
    _git(repo, "update-index", flag, STUDY_CONFIG.as_posix())
    _write_config(repo, True)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True,
        text=True, check=True,
    ).stdout
    assert STUDY_CONFIG.as_posix() not in status  # git status really is blind here
    assert study_config_commit(repo) is None
    study = _study(tmp_path, True)
    assert unlock_evidence(study, repo) is None
    assert not is_test_period_unlocked(study, repo)
    with pytest.raises(LockedPeriodError):
        require_before_test_period("2023-06-01", study, repo)


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_plan_edit_hidden_from_git_status_stays_locked(
    tmp_path: Path, repo: Path, flag: str
) -> None:
    _unlock(repo)
    assert is_test_period_unlocked(_study(tmp_path, True), repo)
    _git(repo, "update-index", flag, PREREGISTRATION_FILE)
    (repo / PREREGISTRATION_FILE).write_text("a different plan, written afterwards\n")
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def _add_clean_filter(repo: Path) -> None:
    """A clean filter kept out of the commit history: git rewrites `true` to
    `false` whenever it reads the config, so git sees the committed content
    while the file on disk says true."""
    # "true" plus one more character becomes "false", so the length is kept
    _git(repo, "config", "filter.hide.clean", "sed 's/unlocked: true./unlocked: false/'")
    info = repo / ".git" / "info"
    info.mkdir(exist_ok=True)
    (info / "attributes").write_text(f"{STUDY_CONFIG.as_posix()} filter=hide\n")


@pytest.mark.parametrize("stage", [True, False])
def test_flag_hidden_by_a_clean_filter_stays_locked(
    tmp_path: Path, repo: Path, stage: bool
) -> None:
    """Second review finding: `git status` and `git hash-object` both run the
    clean filter, so they agree with HEAD while the file on disk says true."""
    _commit_prereg(repo)
    _commit_config(repo, False)
    _add_clean_filter(repo)
    path = repo / STUDY_CONFIG
    # same length as the committed text, so git's size check sees no change
    path.write_text(path.read_text().replace("unlocked: false", "unlocked: true "))
    if stage:
        _git(repo, "add", STUDY_CONFIG.as_posix())
    assert load_study(path).test_period_unlocked  # the disk file does say true
    hashed = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "--", STUDY_CONFIG.as_posix()],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{STUDY_CONFIG.as_posix()}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert hashed == head  # git itself is fooled: the filter hides the edit
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)
    with pytest.raises(LockedPeriodError):
        require_before_test_period("2023-06-01", _study(tmp_path, True), repo)


def test_git_redirected_to_another_repository_stays_locked(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GIT_DIR pointing at a repository where the flag is committed must not
    unlock this one."""
    _commit_prereg(repo)
    _commit_config(repo, False)
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    (other / "README.md").write_text("x\n")
    _git(other, "add", "README.md")
    _git(other, "commit", "-q", "-m", "init")
    _unlock(other)
    assert is_test_period_unlocked(_study(tmp_path, True), other)
    _write_config(repo, True)  # this repository's flag is edited, not committed
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repo))
    assert study_config_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


def test_symlinked_file_stays_locked(tmp_path: Path, repo: Path) -> None:
    _unlock(repo)
    assert is_test_period_unlocked(_study(tmp_path, True), repo)
    path = repo / PREREGISTRATION_FILE
    elsewhere = tmp_path / "plan-elsewhere.md"
    elsewhere.write_text(path.read_text())
    path.unlink()
    path.symlink_to(elsewhere)
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


@pytest.mark.parametrize("text", ["", "   \n\n"])
def test_empty_preregistration_stays_locked(tmp_path: Path, repo: Path, text: str) -> None:
    _commit_config(repo, True)
    (repo / PREREGISTRATION_FILE).write_text(text)
    _git(repo, "add", PREREGISTRATION_FILE)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "empty plan")
    assert preregistration_commit(repo) is None
    assert not is_test_period_unlocked(_study(tmp_path, True), repo)


# Guard: every form of asof ------------------------------------------------


LOCKED_ASOFS = [
    "2022-01-02",
    "2022-01-01 00:00:01",
    pd.Timestamp("2025-01-01"),
    dt.date(2022, 1, 2),
    dt.datetime(2022, 1, 1, 9, 30),
    np.datetime64("2022-01-02"),
    "2100-01-01",
]


@pytest.mark.parametrize("asof", LOCKED_ASOFS, ids=repr)
def test_locked_asof_refused_in_every_form(
    tmp_path: Path, repo: Path, asof: object
) -> None:
    with pytest.raises(LockedPeriodError, match="locked until PREREGISTRATION.md"):
        require_before_test_period(asof, _study(tmp_path, True), repo)


@pytest.mark.parametrize(
    "asof", ["2022-01-01", dt.date(2021, 12, 31), "2018-01-01"], ids=repr
)
def test_asof_up_to_test_start_is_allowed(
    tmp_path: Path, repo: Path, asof: object
) -> None:
    ts = require_before_test_period(asof, _study(tmp_path, False), repo)
    assert ts == to_date(asof) and ts <= TEST_START


def test_timezone_aware_asof_is_refused(tmp_path: Path, repo: Path) -> None:
    aware = pd.Timestamp("2022-01-01 00:30", tz="Asia/Tokyo")  # 2021-12-31 in UTC
    with pytest.raises(TypeError):
        require_before_test_period(aware, _study(tmp_path, False), repo)


@pytest.mark.parametrize("bad", [pd.NaT, "not a date", 20220101, None], ids=repr)
def test_invalid_asof_is_refused(tmp_path: Path, repo: Path, bad: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        require_before_test_period(bad, _study(tmp_path, False), repo)


# Download end and stored rows ---------------------------------------------


def test_download_end_is_clipped_while_locked(tmp_path: Path, repo: Path) -> None:
    locked = _study(tmp_path, True)  # flag set, file missing: still locked
    assert clip_end_to_open_period("2026-11-08", locked, repo) == TEST_START
    assert clip_end_to_open_period("2015-06-01", locked, repo) == pd.Timestamp(
        "2015-06-01"
    )
    _unlock(repo)
    assert clip_end_to_open_period("2026-11-08", locked, repo) == pd.Timestamp(
        "2026-11-08"
    )


def test_rows_already_in_the_test_period_are_dropped(
    tmp_path: Path, repo: Path
) -> None:
    idx = pd.bdate_range("2021-12-27", "2022-01-07", name="date")
    frame = pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)
    study = _study(tmp_path, True)
    kept = drop_locked_rows(frame, study, repo)
    assert kept.index.max() == pd.Timestamp("2021-12-31")
    assert (kept.index < TEST_START).all()
    pd.testing.assert_frame_equal(kept, frame.loc[: "2021-12-31"])
    series = drop_locked_rows(frame["close"], study, repo)
    assert series.index.max() < TEST_START
    _unlock(repo)
    pd.testing.assert_frame_equal(drop_locked_rows(frame, study, repo), frame)


def test_drop_locked_rows_needs_naive_datetime_index(
    tmp_path: Path, repo: Path
) -> None:
    study = _study(tmp_path, False)
    with pytest.raises(TypeError):
        drop_locked_rows(pd.Series([1.0, 2.0]), study, repo)
    aware = pd.Series(
        [1.0], index=pd.DatetimeIndex(["2022-01-03"], tz="America/New_York")
    )
    with pytest.raises(TypeError):
        drop_locked_rows(aware, study, repo)


def test_find_repo_root() -> None:
    assert find_repo_root(REPO_ROOT / "src" / "statarb_agent") == REPO_ROOT
