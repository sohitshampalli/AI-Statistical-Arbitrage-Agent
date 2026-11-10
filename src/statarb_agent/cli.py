"""Command line: `statarb fetch`, `statarb analyse`, `statarb demo`.

The commands only call tested code (analysis.Analyser) and print what it
returned. No number is computed here.

- `statarb fetch TICKER...` downloads tickers that are not cached yet.
- `statarb analyse A B` analyses any two tickers on the formation period,
  downloading what is missing unless --offline, and appends the result to the
  trial log. Pairs not listed in configs/pairs.yaml are labelled exploratory.
- `statarb demo` analyses every demo pair, the control pair and the synthetic
  pair.

Only the formation period is open here. The validation period is opened by
the backtester phase; the test period is locked in the library itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import typer

from statarb_agent.analysis import (
    SURVIVORSHIP_NOTE,
    Analyser,
    OfflineError,
    PairAnalysis,
)
from statarb_agent.project import Project
from statarb_agent.sources.prices import SOURCE, DownloadError
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.study import LockedPeriodError, find_repo_root
from statarb_agent.trials import json_safe

ALLOWED_PERIODS: Final = ("formation",)
LABEL_NOTES: Final = {
    "exploratory": (
        "EXPLORATORY: this pair was chosen by the user and is not pre-registered."
    ),
    "case_study": "CASE STUDY: a demo pair named in the project brief.",
    "control": "CONTROL: a pair with no economic link; no relationship is expected.",
    "synthetic": "SYNTHETIC: simulated data with known parameters, not market data.",
}

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Cointegration pairs research tool. Paper research only; not investment "
    "advice.",
)
_state: dict[str, Path] = {}


@app.callback()
def _main(
    root: Annotated[
        Path | None,
        typer.Option(help="Project folder. Default: the folder holding pyproject.toml."),
    ] = None,
) -> None:
    _state["root"] = root.resolve() if root is not None else find_repo_root()


def _analyser() -> Analyser:
    return Analyser(Project(_state["root"]))


def format_pvalue(p: float) -> str:
    """Three decimals, or scientific notation below 0.001."""
    return f"{p:.3f}" if p >= 0.001 else f"{p:.2e}"


def format_analysis(analysis: PairAnalysis) -> str:
    """Plain-text report of one analysis. Only formats stored values."""
    lines: list[str] = []
    add = lines.append
    add(
        f"{analysis.ticker_a} / {analysis.ticker_b}   period {analysis.period_name}: "
        f"{analysis.start} up to (not including) {analysis.asof}"
    )
    add(LABEL_NOTES[analysis.label])
    if analysis.data_source == SOURCE:
        add(f"Data: yfinance snapshots. {SURVIVORSHIP_NOTE}")
        for ticker in analysis.downloaded:
            add(f"  downloaded {ticker} just now (it was not cached)")
        for ticker, snapshot_id in analysis.snapshot_ids.items():
            add(f"  {ticker}: snapshot {snapshot_id}")
    for flag in analysis.flags():
        add(f"FLAG {flag.name}: {flag.detail} (not corrected)")
    if analysis.outcome != "ok":
        add(f"{analysis.outcome.upper()}: {analysis.reason}")
    stats = analysis.stats
    if stats is not None:
        eg = stats.engle_granger
        fit = stats.spread_ar1
        if fit.mean_reverting and fit.half_life is not None:
            half_life = f"{fit.half_life:.2f} bars"
        else:
            half_life = f"none ({fit.reason})"
        add(f"Rows used: {stats.nobs}, {stats.first_obs} to {stats.last_obs}")
        add(
            f"Hedge ratio ({stats.label_a} on {stats.label_b}): beta "
            f"{stats.hedge.beta:.4f}, alpha {stats.hedge.alpha:.4f}"
        )
        add(
            f"Engle-Granger p-value, {eg.a_on_b.dependent} on {eg.a_on_b.independent}: "
            f"{format_pvalue(eg.a_on_b.pvalue)}; {eg.b_on_a.dependent} on "
            f"{eg.b_on_a.independent}: {format_pvalue(eg.b_on_a.pvalue)}"
        )
        add(
            f"ADF p-value on log-price levels: {stats.label_a} "
            f"{format_pvalue(stats.adf_level_a.pvalue)}, {stats.label_b} "
            f"{format_pvalue(stats.adf_level_b.pvalue)}"
        )
        add(
            f"ADF p-value on log returns: {stats.label_a} "
            f"{format_pvalue(stats.adf_return_a.pvalue)}, {stats.label_b} "
            f"{format_pvalue(stats.adf_return_b.pvalue)}"
        )
        add(f"Spread half-life (in sample): {half_life}")
    if analysis.screen is not None:
        add(f"Screen: {'PASS' if analysis.screen.passed else 'FAIL'}")
        for criterion in analysis.screen.criteria:
            mark = "pass" if criterion.passed else "fail"
            add(f"  [{mark}] {criterion.name}: {criterion.detail}")
        add(
            "A pass describes the formation window only. It is not evidence that "
            "the pair mean-reverts later."
        )
    add(f"Trial log: {analysis.trial_id}")
    return "\n".join(lines)


def _emit(analyses: list[PairAnalysis], as_json: bool) -> None:
    if as_json:
        # json_safe turns an undefined (NaN) statistic into null: strict JSON.
        payload = json_safe([a.to_dict() for a in analyses])
        typer.echo(json.dumps(payload, indent=2, allow_nan=False))
        return
    typer.echo("\n\n".join(format_analysis(a) for a in analyses))


def _fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code=1)


@app.command()
def fetch(
    tickers: Annotated[list[str], typer.Argument(help="Tickers to download.")],
    refresh: Annotated[
        bool,
        typer.Option(help="Download again even if a snapshot exists (a new snapshot)."),
    ] = False,
) -> None:
    """Download daily prices for tickers that are not cached yet."""
    analyser = _analyser()
    try:
        names = list(dict.fromkeys(normalise_ticker(t) for t in tickers))
    except (TypeError, ValueError) as exc:
        raise _fail(f"Invalid ticker: {exc}") from exc
    fetched = 0
    for ticker in names:
        if analyser.is_cached(ticker) and not refresh:
            entry = analyser.source.entry_for(ticker)
            typer.echo(f"{ticker}: already cached, snapshot {entry.snapshot_id}")
            continue
        if fetched:
            analyser.source.sleep(analyser.source.pause_s)
        try:
            snapshot_id = analyser.fetch(ticker)
        except DownloadError as exc:
            raise _fail(str(exc)) from exc
        fetched += 1
        entry = analyser.source.entry_for(ticker)
        typer.echo(
            f"{ticker}: downloaded {entry.n_rows} rows, {entry.first_date[:10]} to "
            f"{entry.last_date[:10]}, snapshot {snapshot_id}"
        )
        for note in entry.notes:
            typer.echo(f"  note: {note}")
    typer.echo(SURVIVORSHIP_NOTE)


@app.command()
def analyse(
    ticker_a: Annotated[str, typer.Argument(help="First ticker (dependent leg).")],
    ticker_b: Annotated[str, typer.Argument(help="Second ticker.")],
    period: Annotated[str, typer.Option(help="Study period to analyse.")] = "formation",
    offline: Annotated[bool, typer.Option(help="Never download.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Analyse any two tickers on the formation period and log the trial."""
    if period not in ALLOWED_PERIODS:
        raise _fail(
            f"Refused: period {period!r} is not open. Only the formation period "
            "(2010 to 2017) can be analysed until the backtester phase."
        )
    analyser = _analyser()
    try:
        analysis = analyser.analyse_pair(
            ticker_a, ticker_b, period_name=period, offline=offline
        )
    except (ValueError, TypeError, OfflineError, LockedPeriodError) as exc:
        raise _fail(str(exc)) from exc
    _emit([analysis], as_json)
    if analysis.outcome != "ok":
        raise typer.Exit(code=2)


@app.command()
def demo(
    offline: Annotated[bool, typer.Option(help="Never download.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Analyse every demo pair, the control pair and the synthetic pair."""
    analyser = _analyser()
    analyses: list[PairAnalysis] = []
    try:
        for pair in analyser.pairs.pairs:
            analyses.append(
                analyser.analyse_pair(pair.a, pair.b, label=pair.label, offline=offline)
            )
    except (OfflineError, LockedPeriodError) as exc:
        raise _fail(str(exc)) from exc
    analyses.append(analyser.analyse_synthetic())
    _emit(analyses, as_json)
    if not as_json:
        typer.echo("\nSummary (formation period, in sample):")
        for a in analyses:
            verdict = (
                a.outcome.upper() if a.screen is None
                else ("screen PASS" if a.screen.passed else "screen FAIL")
            )
            typer.echo(f"  {a.ticker_a}/{a.ticker_b} [{a.label}]: {verdict}")


def main() -> None:
    """Entry point of the `statarb` script."""
    app()
