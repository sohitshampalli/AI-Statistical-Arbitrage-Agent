"""Local dashboard backend: read stored results and serve them as JSON.

Nothing in this package computes a statistic of the research. It reads run
artifacts, the trial log, the configs and the snapshot manifest. The only
derived values (equity and drawdown paths for a chart) are in `series`, which
uses the same definitions as backtest.summary and is tested against it.
"""
