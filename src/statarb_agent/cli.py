"""Command line: fetch, analyse, demo, backtest, backtest-demo, runs, summarise.

The commands only call tested code (analysis.Analyser, backtest.runner) and
print what it returned. No number is computed here.

- `statarb fetch TICKER...` downloads tickers that are not cached yet.
- `statarb analyse A B` analyses any two tickers on the formation period (or
  with --period validation), downloading what is missing unless --offline, and
  appends the result to the trial log. Pairs not listed in configs/pairs.yaml
  are labelled exploratory.
- `statarb demo` analyses every demo pair, the control pair and the synthetic
  pair.
- `statarb backtest A B` runs one walk-forward backtest on the formation and
  validation periods, logs it as a trial and stores a run folder.
- `statarb backtest-demo` runs every pre-stated backtest and control once.
- `statarb runs` lists the stored runs; `statarb summarise` writes a summary of
  them with Deflated Sharpe ratios at the current trial count.

Every analysis and every backtest adds a line to the trial log, so do not
re-run one just to look at a result: `statarb runs` reads the stored results.

The formation and validation periods are open (the validation period since the
backtester phase, 2026-11-11). The test period is locked in the library itself.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Any, Final

import typer

from statarb_agent.analysis import (
    SURVIVORSHIP_NOTE,
    Analyser,
    OfflineError,
    PairAnalysis,
)
from statarb_agent.backtest.config import HEDGES
from statarb_agent.backtest.runner import Backtester, RunRecord
from statarb_agent.backtest.runs import list_runs
from statarb_agent.project import Project
from statarb_agent.sources.prices import SOURCE, DownloadError
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.study import LockedPeriodError, find_repo_root
from statarb_agent.trials import json_safe

ALLOWED_PERIODS: Final = ("formation", "validation")
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
    """Analyse any two tickers on one study period and log the trial."""
    if period not in ALLOWED_PERIODS:
        raise _fail(
            f"Refused: period {period!r} is not open. Use formation (2010 to 2017) "
            "or validation (2018 to 2021). The test period is locked."
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


def format_number(value: Any, pattern: str = "{:.2f}") -> str:
    """Format a stored number, or "n/a" for a missing or undefined one."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return pattern.format(value)


def format_span(name: str, metrics: dict[str, Any] | None, deflated: Any) -> str:
    """One line of metrics for one span of a run."""
    if metrics is None:
        return f"  {name}: no rows in this span"
    line = (
        f"  {name} ({metrics['start']} to {metrics['end']}): net Sharpe "
        f"{format_number(metrics['sharpe'])}, return per year "
        f"{format_number(metrics['annualised_return'], '{:.2%}')}, max drawdown "
        f"{format_number(metrics['max_drawdown'], '{:.2%}')}, trades "
        f"{metrics['n_trades']}, hit rate "
        f"{format_number(metrics['hit_rate'], '{:.0%}')}"
    )
    if deflated:
        line += (
            f", Deflated Sharpe {format_number(deflated['dsr'])} "
            f"({deflated['n_trials']} trials)"
        )
    return line


def format_run(record: RunRecord) -> str:
    """Plain-text report of one backtest run. Only formats stored values."""
    if record.outcome != "ok":
        return f"{record.outcome.upper()}: {record.reason}\nTrial log: {record.run_id}"
    man = record.manifest
    lines: list[str] = []
    add = lines.append
    period = man["period"]
    add(
        f"{' / '.join(man['tickers'])}   backtest, hedge {man['hedge']}, "
        f"{man['cost_bps']:g} bps per leg, {period['start']} up to (not including) "
        f"{period['asof']}"
    )
    add(LABEL_NOTES[man["label"]])
    if man["data_source"] == SOURCE:
        add(f"Data: yfinance snapshots. {SURVIVORSHIP_NOTE}")
        for ticker in man.get("downloaded", []):
            add(f"  downloaded {ticker} just now (it was not cached)")
    screen = man["screen"]
    add(f"Formation-period screen: {screen['status']}")
    for flag in man.get("flags", []):
        add(f"FLAG {flag['name']}: {flag['detail']} (not corrected)")
    deflated = man.get("deflated_sharpe") or {}
    for span in ("formation", "validation", "full"):
        add(format_span(span, man["metrics"].get(span), deflated.get(span)))
    add("Costs are included. Walk-forward: each window is fitted on earlier rows only.")
    add(f"Trial log and run id: {record.run_id}")
    return "\n".join(lines)


def format_run_table(manifests: list[dict[str, Any]]) -> str:
    """One line per stored backtest run or control batch."""
    lines: list[str] = []
    for man in manifests:
        if man["kind"] == "backtest":
            validation = man["metrics"].get("validation") or {}
            formation = man["metrics"].get("formation") or {}
            lines.append(
                f"{man['run_id']}  {'/'.join(man['tickers'])} [{man['label']}] "
                f"{man['hedge']} {man['cost_bps']:g}bps  screen {man['screen']['status']}"
                f"  net Sharpe formation {format_number(formation.get('sharpe'))}, "
                f"validation {format_number(validation.get('sharpe'))}"
            )
        elif man["kind"] == "control_batch":
            summary = man["summary"]
            lines.append(
                f"{man['run_id']}  {'/'.join(man['tickers'])} [{man['control']} batch] "
                f"{man['hedge']} {man['cost_bps']:g}bps  {summary['n_seeds']} seeds, "
                f"mean net Sharpe {format_number(summary['mean_sharpe'])}, positive "
                f"{format_number(summary['share_positive'], '{:.1%}')}"
            )
        else:
            lines.append(
                f"{man['run_id']}  summary of {len(man['rows'])} runs, "
                f"{man['n_trials_counted']} counted trials"
            )
    return "\n".join(lines) if lines else "No stored runs. Run `statarb backtest A B`."


@app.command()
def backtest(
    ticker_a: Annotated[str, typer.Argument(help="First ticker (dependent leg).")],
    ticker_b: Annotated[str, typer.Argument(help="Second ticker.")],
    hedge: Annotated[
        str | None, typer.Option(help="static, rolling or kalman. Default: config.")
    ] = None,
    cost_bps: Annotated[
        float | None, typer.Option(help="Cost per leg in basis points. Default: config.")
    ] = None,
    offline: Annotated[bool, typer.Option(help="Never download.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """Walk-forward backtest of any two tickers; logged as a trial."""
    if hedge is not None and hedge not in HEDGES:
        raise _fail(f"Refused: hedge must be one of {', '.join(HEDGES)}.")
    if cost_bps is not None and not cost_bps >= 0.0:
        raise _fail("Refused: cost-bps must be zero or more.")
    runner = Backtester(_analyser())
    try:
        record = runner.backtest_pair(
            ticker_a, ticker_b, hedge=hedge, cost_bps=cost_bps, offline=offline
        )
    except (ValueError, TypeError, OfflineError, LockedPeriodError) as exc:
        raise _fail(str(exc)) from exc
    if as_json:
        payload = {"run_id": record.run_id, "outcome": record.outcome,
                   "reason": record.reason, "manifest": record.manifest}
        typer.echo(json.dumps(json_safe(payload), indent=2, allow_nan=False))
    else:
        typer.echo(format_run(record))
    if record.outcome != "ok":
        raise typer.Exit(code=2)


@app.command("backtest-demo")
def backtest_demo(
    offline: Annotated[bool, typer.Option(help="Never download.")] = False,
    again: Annotated[
        bool,
        typer.Option(help="Run even if this config's demo is already in the trial log."),
    ] = False,
) -> None:
    """Run every pre-stated backtest and control once, then write a summary."""
    runner = Backtester(_analyser())
    if runner.demo_already_run() and not again:
        raise _fail(
            "Refused: the trial log already holds the demo backtests for this "
            "configs/backtest.yaml. Running them again would log every trial twice. "
            "Use `statarb runs` to read the stored results, or pass --again."
        )
    try:
        records = runner.run_demo(offline=offline)
    except (OfflineError, LockedPeriodError) as exc:
        raise _fail(str(exc)) from exc
    summary = runner.summarise()
    typer.echo(format_run_table([r.manifest for r in records if r.outcome == "ok"]))
    for record in records:
        if record.outcome != "ok":
            typer.echo(f"{record.run_id}  {record.outcome.upper()}: {record.reason}")
    typer.echo("")
    typer.echo(summary.manifest["headline"]["statement"])
    typer.echo(f"Summary: {summary.run_id}")


@app.command()
def runs() -> None:
    """List the stored runs. Reads artifacts only; adds no trial."""
    typer.echo(format_run_table(list_runs(Project(_state["root"]).runs_dir)))


@app.command()
def summarise() -> None:
    """Write a summary of all stored backtest runs. Adds no trial."""
    summary = Backtester(_analyser()).summarise()
    manifest = summary.manifest
    typer.echo(
        f"{len(manifest['rows'])} backtest runs; {manifest['n_trials_counted']} "
        "real-data backtest trials counted for the Deflated Sharpe ratio."
    )
    typer.echo(manifest["headline"]["statement"])
    typer.echo(f"Summary: {summary.run_id}")


def main() -> None:
    """Entry point of the `statarb` script."""
    app()
