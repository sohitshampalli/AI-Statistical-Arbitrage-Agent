"""Tests for the dashboard API on a fake project filled by the real runner."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from fake_market import REPO_ROOT
from fake_results import FakeResults, make_results, make_runner
from fastapi.testclient import TestClient

from statarb_agent.api import app as app_module
from statarb_agent.api.app import create_app
from statarb_agent.backtest.runs import list_runs, read_manifest

BASE = "http://127.0.0.1:8000"


def client_for(root: Path, **kwargs) -> TestClient:
    return TestClient(create_app(root, **kwargs), base_url=BASE)


def with_gates(root: Path) -> None:
    (root / "docs").mkdir(exist_ok=True)
    shutil.copy(REPO_ROOT / "docs" / "gates.yaml", root / "docs" / "gates.yaml")


@pytest.fixture
def results(tmp_path: Path) -> FakeResults:
    out = make_results(tmp_path)
    with_gates(out.project.root)
    return out


@pytest.fixture
def client(results: FakeResults) -> TestClient:
    return client_for(results.project.root)


@pytest.fixture(scope="module")
def demo_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fake project after the full demo: every run kind the runner writes."""
    runner = make_runner(tmp_path_factory.mktemp("demo"))
    runner.run_demo()
    runner.summarise()
    with_gates(runner.project.root)
    return runner.project.root


def assert_error(response, status: int, error: str, endpoint: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error", "message", "endpoint", "run_id"}
    assert body["error"] == error and body["endpoint"] == endpoint and body["message"]
    return body


# Every stored manifest fits the contract ----------------------------------


def test_every_run_the_demo_writes_validates_against_the_schema(demo_root: Path) -> None:
    client = client_for(demo_root)
    manifests = list_runs(demo_root / "reports" / "runs")
    kinds = {(m["kind"], m.get("strategy"), m.get("control")) for m in manifests}
    assert ("backtest", "pair", None) in kinds and ("backtest", "basket", None) in kinds
    assert ("control_batch", None, "placebo") in kinds and ("summary", None, None) in kinds
    for man in manifests:
        response = client.get(f"/api/runs/{man['run_id']}")
        assert response.status_code == 200, response.text
        served = response.json()
        # the schema forbids unknown keys, so nothing stored was dropped
        assert set(man) <= set(served)
        assert served["run_id"] == man["run_id"]
    assert client.get("/api/summary/latest").json()["kind"] == "summary"


# Meta and lists -----------------------------------------------------------


def test_meta_reports_counts_lock_and_data(results: FakeResults, client: TestClient) -> None:
    meta = client.get("/api/meta").json()
    trials = results.runner.log.read()
    assert meta["trials_in_log"] == len(trials)
    assert meta["trials_counted"] == results.summary.manifest["n_trials_counted"]
    assert meta["latest_summary_id"] == results.summary.run_id
    assert meta["summary_stale"] is False
    assert meta["study"]["test_start"] == "2022-01-01"
    assert meta["study"]["test_period_locked"] is True
    assert meta["downloads_enabled"] is False and meta["paper_trading_only"] is True
    assert meta["data_first_date"] == "2010-01-04"
    assert meta["data_last_date"] == "2021-12-31"
    # a new counted attempt makes the stored summary's trial count stale
    results.runner.analyser.analyse_pair("KO", "PEP")
    meta = client.get("/api/meta").json()
    assert meta["trials_counted"] == results.summary.manifest["n_trials_counted"] + 1
    assert meta["summary_stale"] is True


def test_runs_filters_and_staleness(
    results: FakeResults, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = client.get("/api/runs").json()["runs"]
    assert {r["run_id"] for r in runs} == {results.pair_run.run_id, results.summary.run_id}
    only = client.get("/api/runs", params={"kind": "backtest", "ticker": "aaa"}).json()
    assert [r["run_id"] for r in only["runs"]] == [results.pair_run.run_id]
    assert client.get("/api/runs", params={"cost_bps": 20}).json()["runs"] == []
    assert all(r["stale"] is False for r in runs)  # same (unknown) commit
    monkeypatch.setattr(app_module, "_head", lambda root: ("a" * 40, False))
    assert all(r["stale"] for r in client.get("/api/runs").json()["runs"])
    assert client.get(f"/api/runs/{results.pair_run.run_id}").json()["stale"] is True


# One run ------------------------------------------------------------------


def test_run_and_compare(results: FakeResults, client: TestClient) -> None:
    rid, sid = results.pair_run.run_id, results.summary.run_id
    run = client.get(f"/api/runs/{rid}").json()
    stored = read_manifest(results.project.runs_dir, rid)
    assert run["metrics"]["validation"]["sharpe"] == stored["metrics"]["validation"]["sharpe"]
    assert run["provenance"] == stored["provenance"]
    both = client.get("/api/compare", params={"a": rid, "b": sid}).json()
    assert both["a"]["run_id"] == rid and both["b"]["kind"] == "summary"


def test_unknown_and_malformed_run_ids(client: TestClient) -> None:
    missing = "20991231T000000000000Z-00000000"
    body = assert_error(client.get(f"/api/runs/{missing}"), 404, "not_found",
                        f"/api/runs/{missing}")
    assert body["run_id"] == missing
    # a path in the id does not match the route, so it never reaches the disk
    assert_error(client.get("/api/runs/..%2F..%2Fconfigs"), 404, "not_found",
                 "/api/runs/../../configs")
    assert_error(client.get("/api/runs/..."), 400, "bad_run_id", "/api/runs/...")
    assert_error(client.get("/api/runs/not-a-run/tables/daily"), 400, "bad_run_id",
                 "/api/runs/not-a-run/tables/daily")


def test_tables_columns_dates_and_refusals(results: FakeResults, client: TestClient) -> None:
    rid = results.pair_run.run_id
    url = f"/api/runs/{rid}/tables/daily"
    full = client.get(url).json()
    files = read_manifest(results.project.runs_dir, rid)["files"]
    assert full["sha256"] == files["daily"]["sha256"]
    assert len(full["index"]) == files["daily"]["rows"]
    assert set(full["columns"]) == set(files["daily"]["columns"])
    part = client.get(url, params={"columns": "ret,equity", "start": "2018-01-01",
                                   "end": "2018-01-31"}).json()
    assert set(part["columns"]) == {"ret", "equity"}
    assert part["index"][0] >= "2018-01-01" and part["index"][-1] <= "2018-01-31"
    assert len(part["columns"]["ret"]) == len(part["index"]) > 0
    trades = client.get(f"/api/runs/{rid}/tables/trades").json()
    assert isinstance(trades["columns"]["exit_date"][0], (str, type(None)))
    assert_error(client.get(url, params={"columns": "nope"}), 400, "bad_request", url)
    assert_error(client.get(f"/api/runs/{rid}/tables/trades", params={"start": "2018-01-01"}),
                 400, "bad_request", f"/api/runs/{rid}/tables/trades")
    assert_error(client.get(f"/api/runs/{rid}/tables/secrets"), 404, "not_found",
                 f"/api/runs/{rid}/tables/secrets")
    # a table name with a path in it never reaches the file system
    response = client.get(f"/api/runs/{rid}/tables/..%2Frun.json")
    assert response.status_code == 404 and response.json()["error"] == "not_found"


def test_a_damaged_table_is_an_integrity_error_naming_the_run(
    results: FakeResults, client: TestClient
) -> None:
    rid = results.pair_run.run_id
    path = results.project.runs_dir / rid / "daily.parquet"
    path.write_bytes(path.read_bytes() + b"x")
    for url in (f"/api/runs/{rid}/tables/daily", f"/api/runs/{rid}/series/equity"):
        body = assert_error(client.get(url), 500, "integrity", url)
        assert body["run_id"] == rid and "does not match" in body["message"]


def test_equity_series_matches_the_stored_span(results: FakeResults, client: TestClient) -> None:
    rid = results.pair_run.run_id
    stored = read_manifest(results.project.runs_dir, rid)["metrics"]
    for span in ("full", "formation", "validation"):
        series = client.get(f"/api/runs/{rid}/series/equity", params={"span": span}).json()
        assert series["start"] == stored[span]["start"]
        assert len(series["dates"]) == stored[span]["n_days"]
        drawdowns = [d for d in series["drawdown"] if d is not None]
        assert max(drawdowns) == pytest.approx(series["stored_max_drawdown"], abs=1e-12)
        assert series["equity"][-1] - 1.0 == pytest.approx(stored[span]["total_return"])
        assert series["cost_bps"] == 10.0
    url = f"/api/runs/{rid}/series/equity"
    assert_error(client.get(url, params={"span": "test"}), 400, "bad_request", url)
    sid = results.summary.run_id
    assert_error(client.get(f"/api/runs/{sid}/series/equity"), 400, "bad_request",
                 f"/api/runs/{sid}/series/equity")


# Trials, pairs, configs, gates, data --------------------------------------


def test_trials_paging_filters_and_counting(results: FakeResults, client: TestClient) -> None:
    trials = results.runner.log.read()
    page = client.get("/api/trials", params={"limit": 2}).json()
    assert page["total"] == len(trials) and len(page["items"]) == 2
    assert [i["line"] for i in page["items"]] == [1, 2]
    assert page["items"][0]["trial_id"] == trials[0].trial_id
    everything = client.get("/api/trials", params={"limit": 500}).json()["items"]
    stats = client.get("/api/trials/stats").json()
    assert sum(i["counted"] for i in everything) == stats["n_backtests_counted"]
    assert stats["n_counted"] == results.summary.manifest["n_trials_counted"]
    assert "never backtested" in stats["counting_rule"]
    only = client.get("/api/trials", params={"kind": "backtest", "ticker": "bbb"}).json()
    assert only["total"] == 1 and only["items"][0]["tickers"] == ["AAA", "BBB"]
    assert_error(client.get("/api/trials", params={"limit": 501}), 400, "bad_request",
                 "/api/trials")


def test_pairs_configs_and_data(results: FakeResults, client: TestClient) -> None:
    pairs = client.get("/api/pairs").json()
    v_ma = next(p for p in pairs["pairs"] if (p["a"], p["b"]) == ("V", "MA"))
    assert v_ma["screen"]["status"] in ("pass", "fail") and v_ma["screen"]["trial_id"]
    configs = {c["name"]: c for c in client.get("/api/configs").json()["configs"]}
    assert configs["backtest"]["sha256"] == results.project.config_hashes()["backtest"]
    data = client.get("/api/data").json()
    (yahoo,) = data["sources"]
    assert yahoo["downloads_enabled"] is False and yahoo["terms_checked_on"] == "2026-11-23"
    assert "AAA" in data["cached_tickers"] and "SPY" in data["cached_tickers"]
    assert all(x["downloaded_before_terms_check"] for x in data["snapshots"])


def test_gates_and_their_evidence_tests_exist(client: TestClient) -> None:
    gates = client.get("/api/gates").json()["gates"]
    assert [g["phase"] for g in gates[:3]] == ["1", "2", "3"]
    assert all(g["status"] == "passed" and g["passed_on"] for g in gates[:3])
    for gate in gates:
        for node in gate["evidence"]:
            path, name = node.split("::")
            assert f"def {name}(" in (REPO_ROOT / path).read_text(), node


def test_gates_file_matches_the_brief_dates() -> None:
    raw = yaml.safe_load((REPO_ROOT / "docs" / "gates.yaml").read_text())
    dates = {g["phase"]: g["passed_on"] for g in raw["gates"]}
    assert dates["1"] == "2026-11-06" and dates["2"] == "2026-11-10"
    assert dates["3"] == "2026-11-23"


# Local-only safety ---------------------------------------------------------


def test_a_foreign_host_is_refused(results: FakeResults) -> None:
    rebinding = TestClient(create_app(results.project.root), base_url="http://evil.example:8000")
    assert_error(rebinding.get("/api/meta"), 403, "forbidden", "/api/meta")
    wrong_port = TestClient(create_app(results.project.root), base_url="http://127.0.0.1:9999")
    assert wrong_port.get("/api/meta").status_code == 403
    localhost = TestClient(create_app(results.project.root), base_url="http://localhost:8000")
    assert localhost.get("/api/meta").status_code == 200


def test_a_foreign_origin_is_refused(client: TestClient, results: FakeResults) -> None:
    evil = client.get("/api/meta", headers={"Origin": "https://evil.example"})
    assert_error(evil, 403, "forbidden", "/api/meta")
    assert client.get("/api/meta", headers={"Origin": BASE}).status_code == 200
    vite = {"Origin": "http://localhost:5173"}
    assert client.get("/api/meta", headers=vite).status_code == 403
    dev = client_for(results.project.root, dev=True)
    assert dev.get("/api/meta", headers=vite).status_code == 200


def test_reading_endpoints_take_no_writes_and_no_docs_are_served(client: TestClient) -> None:
    assert client.post("/api/meta").status_code == 405
    assert client.delete("/api/runs").status_code == 405
    for url in ("/docs", "/redoc", "/openapi.json"):
        assert_error(client.get(url), 404, "not_found", url)
