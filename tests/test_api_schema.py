"""The committed JSON Schema of the API must match the pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fake_market import REPO_ROOT

from statarb_agent.api import schema_export
from statarb_agent.api.schema_export import SCHEMA_PATH, response_models, schema_text


def test_committed_schema_matches_the_models() -> None:
    committed = (REPO_ROOT / SCHEMA_PATH).read_text(encoding="utf-8")
    assert committed == schema_text(), (
        "frontend/src/api/schema.json is out of date: run "
        "`uv run python -m statarb_agent.api.schema_export` and commit it"
    )


def test_every_model_is_in_the_schema() -> None:
    document = json.loads(schema_text())
    names = {model.__name__ for model in response_models()}
    assert {"Meta", "RunManifest", "Table", "EquitySeries", "ErrorBody"} <= names
    assert names <= set(document["$defs"])


def test_schema_forbids_unknown_keys() -> None:
    document = json.loads(schema_text())
    assert document["$defs"]["RunManifest"]["additionalProperties"] is False


def test_check_mode_detects_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert schema_export.main(["--check"]) == 1  # no file yet
    assert schema_export.main([]) == 0
    assert schema_export.main(["--check"]) == 0
    path = tmp_path / SCHEMA_PATH
    path.write_text(path.read_text().replace('"Meta"', '"Meta2"', 1))
    assert schema_export.main(["--check"]) == 1
