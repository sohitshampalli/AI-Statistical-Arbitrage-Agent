"""A throwaway project with stored results, for the dashboard backend tests.

Not a test module. It runs the real analysis and backtest code on the fake
market (tests/fake_market.py), so every number the API serves in these tests
comes from tested code, never from a hand-written fixture.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from fake_market import FakeDownloader, base_frames, make_project

from statarb_agent.analysis import Analyser
from statarb_agent.backtest.runner import Backtester, RunRecord
from statarb_agent.project import Project
from statarb_agent.sources.base import SnapshotStore
from statarb_agent.sources.prices import YFinancePrices
from statarb_agent.study import load_study
from statarb_agent.trials import TrialLog

# Before the Yahoo terms were checked (2026-11-23), like the real snapshots.
RETRIEVED_BEFORE_TERMS = pd.Timestamp("2026-11-10T09:00:00", tz="UTC")


@dataclass
class FakeResults:
    """A project folder, the runner that filled it and the records it wrote."""

    project: Project
    runner: Backtester
    pair_run: RunRecord
    summary: RunRecord


def make_runner(
    tmp_path: Path, *, clock: Callable[[], pd.Timestamp] | None = None
) -> Backtester:
    """A Backtester on a fresh fake project with small control batches."""
    project = make_project(tmp_path, small_controls=True)
    study = load_study(project.study_path)
    source = YFinancePrices(
        SnapshotStore(project.data_dir, repo_root=project.root), study=study,
        downloader=FakeDownloader(base_frames()), pause_s=0.0,
        clock=clock or (lambda: RETRIEVED_BEFORE_TERMS),
    )
    return Backtester(Analyser(project, source=source, log=TrialLog(project.trials_path)))


def make_results(tmp_path: Path) -> FakeResults:
    """Analyse V/MA, backtest AAA/BBB, and write a summary."""
    runner = make_runner(tmp_path)
    runner.analyser.analyse_pair("V", "MA")
    pair_run = runner.backtest_pair("AAA", "BBB")
    summary = runner.summarise()
    return FakeResults(runner.project, runner, pair_run, summary)
