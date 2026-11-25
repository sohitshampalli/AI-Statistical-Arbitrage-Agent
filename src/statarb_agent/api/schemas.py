"""Response models of the dashboard API, one per endpoint.

These pydantic models are the contract between the backend and the frontend.
They are exported to JSON Schema (api.schema_export) and mirrored as
TypeScript types; a test fails if the committed schema drifts from them.

Fields mirror what the project already stores (run.json, the trial log, the
manifest); nothing here adds a number. Free-form parts that differ by run kind
or config (settings, batch summaries) stay plain dicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Number = float | None


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Shared parts -------------------------------------------------------------


class Provenance(Model):
    """Which code, configs and data produced a result."""

    code_commit: str
    code_dirty: bool
    config_hashes: dict[str, str]
    snapshot_ids: dict[str, str] | None = None
    trial_id: str | None = None


class Period(Model):
    name: str
    start: str
    asof: str


class SpanMetrics(Model):
    """Metrics of one span, as backtest.summary.span_metrics stores them."""

    start: str
    end: str
    n_days: int
    total_return: Number
    annualised_return: Number
    annualised_volatility: Number
    sharpe: Number
    sharpe_per_period: Number
    gross_sharpe: Number
    sortino: Number
    max_drawdown: Number
    calmar: Number
    skewness: Number
    kurtosis: Number
    psr_zero: Number
    n_trades: int
    hit_rate: Number
    average_holding_bars: Number
    annual_turnover: Number
    cost_drag: Number
    beta_to_benchmark: Number
    share_in_market: Number
    average_gross_exposure: Number
    average_abs_net_exposure: Number
    price_return: Number
    distribution_return: Number
    trade_cost_return: Number
    borrow_cost_return: Number
    exit_reasons: dict[str, int]


class DeflatedSharpe(Model):
    dsr: Number
    expected_max: Number
    n_defined: int
    n_trials: int
    sharpe_variance: Number


class ScreenCriterion(Model):
    name: str
    passed: bool
    detail: str


class ScreenStatus(Model):
    """Latest formation-period screen result of a ticker set."""

    status: Literal["pass", "fail", "refused", "error", "not_analysed"]
    trial_id: str | None
    criteria: list[ScreenCriterion]
    reason: str | None


class TableFile(Model):
    file: str
    sha256: str
    rows: int
    columns: list[str]


class OpenAtEnd(Model):
    open: bool
    exit_cost_not_charged_return: Number
    unrealised_net_pnl_return: Number


class PlaceboRank(Model):
    real_sharpe: Number
    n_placebos: Number
    placebo_mean: Number
    share_at_least: Number


class HeadlineCandidate(Model):
    tickers: list[str]
    state: str
    run_id: str | None
    reason: str | None
    # absent when no run is stored for the candidate
    screen_status: str | None = None
    screen_status_at_run: str | None = None


class Headline(Model):
    """The strategy as stated in advance (backtest.runner, the summary)."""

    statement: str
    complete: bool
    n_candidates: int
    n_runs: int
    candidate_states: dict[str, int]
    candidates: list[HeadlineCandidate]
    run_ids: list[str]
    duplicate_run_ids_ignored: list[str]
    out_of_sample_span: str
    spans_in_sample_for_screen: list[str]
    metrics: dict[str, SpanMetrics | None] | None
    deflated_sharpe: dict[str, DeflatedSharpe | None] | None


class SummaryRow(Model):
    run_id: str
    tickers: list[str]
    label: str
    strategy: str
    hedge: str
    cost_bps: float
    data_source: str
    screen_status: str | None
    screen_status_at_run: str | None
    metrics: dict[str, SpanMetrics | None]
    deflated_sharpe: dict[str, DeflatedSharpe | None] | None
    open_at_end: OpenAtEnd | None


# One run ------------------------------------------------------------------


class RunManifest(Model):
    """run.json of a backtest, control batch or summary.

    Fields that a kind does not have are null. A test checks that every key
    the runner writes is a field here, so nothing is dropped silently.
    """

    run_id: str
    kind: Literal["backtest", "control_batch", "summary"]
    schema_version: int
    created_at_utc: str
    provenance: Provenance
    files: dict[str, TableFile]
    stale: bool = False
    # backtest and control batch
    label: str | None = None
    tickers: list[str] | None = None
    period: Period | None = None
    data_source: str | None = None
    survivorship_bias: bool | None = None
    settings: dict[str, Any] | None = None
    hedge: str | None = None
    cost_bps: float | None = None
    # backtest
    strategy: str | None = None
    metrics: dict[str, SpanMetrics | None] | None = None
    deflated_sharpe: dict[str, DeflatedSharpe | None] | None = None
    screen: ScreenStatus | None = None
    open_at_end: OpenAtEnd | None = None
    spans_in_sample_for_screen: list[str] | None = None
    n_windows: int | None = None
    first_signal_date: str | None = None
    flags: list[dict[str, Any]] | None = None
    downloaded: list[str] | None = None
    # control batch
    control: str | None = None
    summary: dict[str, Any] | None = None
    real_run_id: str | None = None
    real_sharpe: Number = None
    rank: dict[str, PlaceboRank] | None = None
    # summary
    headline: Headline | None = None
    rows: list[SummaryRow] | None = None
    n_trials_counted: int | None = None
    n_trials_in_log: int | None = None
    n_backtests_counted: int | None = None
    default_hedge: str | None = None
    default_cost_bps: float | None = None
    out_of_sample_span: str | None = None
    exploratory_screened_run_ids: list[str] | None = None
    screened_not_backtested: list[list[str]] | None = None
    unlisted_case_study_run_ids: list[str] | None = None


class RunListItem(Model):
    run_id: str
    kind: str
    label: str | None
    tickers: list[str] | None
    strategy: str | None
    hedge: str | None
    cost_bps: float | None
    control: str | None
    data_source: str | None
    created_at_utc: str | None
    code_commit: str | None
    code_dirty: bool | None
    stale: bool


class RunList(Model):
    runs: list[RunListItem]


class RunCompare(Model):
    a: RunManifest
    b: RunManifest


class Table(Model):
    """One stored table as columns. Dates are ISO strings; NaN is null."""

    run_id: str
    name: str
    sha256: str
    index_name: str | None
    index: list[str | int]
    columns: dict[str, list[float | int | str | bool | None]]


class EquitySeries(Model):
    """Equity and drawdown of one span, as fractions of the fixed capital."""

    run_id: str
    span: str
    start: str
    end: str
    cost_bps: float | None
    dates: list[str]
    equity: list[Number]
    gross_equity: list[Number]
    drawdown: list[Number]
    stored_max_drawdown: Number
    stored_total_return: Number
    provenance: Provenance


# Trials -------------------------------------------------------------------


class TrialItem(Model):
    """One line of the trial log, with its 1-based line number."""

    line: int
    trial_id: str
    recorded_at_utc: str
    kind: str
    label: str | None
    tickers: list[str]
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
    parameters: dict[str, Any]
    results: dict[str, Any]
    counted: bool
    schema_version: int


class TrialPage(Model):
    total: int
    offset: int
    limit: int
    items: list[TrialItem]


class TrialStats(Model):
    n_lines: int
    by_kind: dict[str, int]
    by_label: dict[str, int]
    by_outcome: dict[str, int]
    n_backtests_counted: int
    n_screened_not_backtested: int
    n_counted: int
    dirty_lines: list[int]
    counting_rule: str


# Pairs, configs, gates, data ----------------------------------------------


class PairEntry(Model):
    a: str
    b: str
    label: str
    screen: ScreenStatus


class BasketEntry(Model):
    tickers: list[str]
    screen: ScreenStatus


class SyntheticEntry(Model):
    a: str
    b: str
    label: str
    seed: int
    beta: float
    half_life: float
    screen: ScreenStatus


class Pairs(Model):
    pairs: list[PairEntry]
    basket: BasketEntry
    synthetic: SyntheticEntry


class ConfigFile(Model):
    name: str
    path: str
    sha256: str
    text: str


class Configs(Model):
    configs: list[ConfigFile]


class Gate(Model):
    phase: str
    title: str
    gate: str
    status: Literal["passed", "not_started", "in_progress"]
    passed_on: str | None
    evidence: list[str]


class Gates(Model):
    gates: list[Gate]


class SourceInfoModel(Model):
    name: str
    title: str
    downloads_enabled: bool
    terms_checked_on: str | None
    terms_note: str
    reference: str


class Snapshot(Model):
    snapshot_id: str
    source: str
    key: str
    retrieved_at_utc: str
    first_date: str | None
    last_date: str | None
    n_rows: int
    url: str
    file_present: bool
    downloaded_before_terms_check: bool | None


class DataProvenance(Model):
    sources: list[SourceInfoModel]
    snapshots: list[Snapshot]
    cached_tickers: list[str]


# Meta ---------------------------------------------------------------------


class StudyPeriods(Model):
    formation_start: str
    formation_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_period_locked: bool


class Meta(Model):
    """State of the project when the page loads."""

    project: str
    head_commit: str
    head_dirty: bool
    study: StudyPeriods
    trials_in_log: int
    trials_counted: int
    latest_summary_id: str | None
    latest_summary_trials_counted: int | None
    summary_stale: bool
    data_first_date: str | None
    data_last_date: str | None
    downloads_enabled: bool
    paper_trading_only: bool


class ErrorBody(Model):
    """Every error response: a plain message with the endpoint and run id."""

    error: str
    message: str
    endpoint: str
    run_id: str | None = None
