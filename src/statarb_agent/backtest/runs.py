"""Run artifacts: the stored results that the dashboard reads.

Every backtest run, control batch and summary is written once to

    reports/runs/<run_id>/run.json        what was run, with what, and the metrics
    reports/runs/<run_id>/<name>.parquet  the tables (ledger, trades, signals, ...)

`run.json` lists every table with its SHA-256, and a table is checked against
it when read. A run folder is never changed after it is written: the files are
written to a temporary folder that is renamed into place, and an existing run
id is refused.

Runs are derived from downloaded prices, so the folder is not committed to git
(only the code, the configs, the manifest and the trial log are).

Nothing here computes a statistic. Numbers in run.json come from tested code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Final

import pandas as pd

from statarb_agent.trials import json_safe

RUN_SCHEMA_VERSION: Final = 1
MANIFEST_NAME: Final = "run.json"
RUN_KINDS: Final = ("backtest", "control_batch", "summary")
_RUN_ID: Final = re.compile(r"\d{8}T\d{12}Z-[0-9a-f]{8}")
_TABLE_NAME: Final = re.compile(r"[a-z][a-z0-9_]*")


class RunError(RuntimeError):
    """A run artifact is missing, damaged or would be overwritten."""


def _check_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ValueError(f"invalid run id {run_id!r}")
    return run_id


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run(
    runs_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    tables: dict[str, pd.DataFrame],
) -> Path:
    """Write one run folder and return its path.

    Args:
        runs_dir: The reports/runs folder (created if missing).
        run_id: Id of the run; a trial id, or an id made the same way.
        manifest: Contents of run.json. Must hold "kind". The keys
            schema_version, run_id and files are added here.
        tables: Parquet tables to store, by name (lowercase letters, digits
            and underscores).

    Raises:
        ValueError: On an invalid id, kind or table name.
        RunError: If the run id already exists.
    """
    _check_id(run_id)
    if manifest.get("kind") not in RUN_KINDS:
        raise ValueError(f"manifest kind must be one of {RUN_KINDS}")
    for name in tables:
        if not _TABLE_NAME.fullmatch(name):
            raise ValueError(f"invalid table name {name!r}")
    runs_dir = Path(runs_dir)
    final = runs_dir / run_id
    if final.exists():
        raise RunError(f"run {run_id} already exists; runs are never overwritten")
    runs_dir.mkdir(parents=True, exist_ok=True)
    tmp = runs_dir / f".tmp-{run_id}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        files: dict[str, dict[str, Any]] = {}
        for name, table in tables.items():
            path = tmp / f"{name}.parquet"
            table.to_parquet(path, index=True)
            files[name] = {
                "file": path.name, "sha256": _sha256(path), "rows": len(table),
                "columns": [str(c) for c in table.columns],
            }
        content = {
            **manifest,
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "files": files,
        }
        text = json.dumps(json_safe(content), indent=2, sort_keys=True, allow_nan=False)
        (tmp / MANIFEST_NAME).write_text(text + "\n", encoding="utf-8")
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def read_manifest(runs_dir: Path, run_id: str) -> dict[str, Any]:
    """Read run.json of one run.

    Raises:
        RunError: If the run or its manifest is missing, is not valid JSON, or
            has an unknown schema version or a different run id inside.
    """
    path = Path(runs_dir) / _check_id(run_id) / MANIFEST_NAME
    if not path.is_file():
        raise RunError(f"no run {run_id} in {runs_dir}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunError(f"{path} is not valid JSON") from exc
    if manifest.get("schema_version") != RUN_SCHEMA_VERSION:
        raise RunError(f"{path} has an unsupported schema version")
    if manifest.get("run_id") != run_id:
        raise RunError(f"{path} belongs to another run")
    return manifest


def read_table(runs_dir: Path, run_id: str, name: str) -> pd.DataFrame:
    """Read one table of a run after checking its SHA-256.

    Raises:
        RunError: If the table is not listed, is missing or fails the check.
    """
    manifest = read_manifest(runs_dir, run_id)
    entry = manifest["files"].get(name)
    if entry is None:
        raise RunError(f"run {run_id} has no table {name!r}")
    path = Path(runs_dir) / run_id / entry["file"]
    if not path.is_file():
        raise RunError(f"{path} is missing")
    if _sha256(path) != entry["sha256"]:
        raise RunError(f"{path} does not match the hash in run.json")
    return pd.read_parquet(path)


def list_runs(runs_dir: Path) -> list[dict[str, Any]]:
    """Manifests of every run, oldest first. A missing folder is an empty list."""
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        return []
    ids = sorted(p.name for p in runs_dir.iterdir() if _RUN_ID.fullmatch(p.name))
    return [read_manifest(runs_dir, run_id) for run_id in ids]
