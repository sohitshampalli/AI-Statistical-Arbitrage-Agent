"""Tests for starting the dashboard: build check, localhost binding, static files."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fake_results import make_runner
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from statarb_agent import cli
from statarb_agent.api import server
from statarb_agent.api.app import create_app
from statarb_agent.api.server import (
    DashboardError,
    build_frontend,
    needs_build,
    run_dashboard,
)

BASE = "http://127.0.0.1:8000"


def built_frontend(root: Path) -> Path:
    frontend = root / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "main.tsx").write_text("x")
    (frontend / "dist").mkdir()
    (frontend / "dist" / "index.html").write_text("<!doctype html><title>dash</title>")
    os.utime(frontend / "src" / "main.tsx", (1_000_000, 1_000_000))
    return frontend


def test_needs_build_follows_the_inputs(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "a.ts").write_text("x")
    assert needs_build(frontend)  # nothing built
    (frontend / "dist").mkdir()
    index = frontend / "dist" / "index.html"
    index.write_text("built")
    os.utime(frontend / "src" / "a.ts", (1_000_000, 1_000_000))
    assert not needs_build(frontend)
    (frontend / "package.json").write_text("{}")  # newer than the build
    assert needs_build(frontend)


def test_build_refuses_without_installed_packages(tmp_path: Path) -> None:
    with pytest.raises(DashboardError, match="npm ci"):
        build_frontend(tmp_path)
    (tmp_path / "node_modules").mkdir()
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs["cwd"]))
        return SimpleNamespace(returncode=1)

    with pytest.raises(DashboardError, match="build failed"):
        build_frontend(tmp_path, run=run)
    assert calls == [(["npm", "run", "build"], tmp_path)]


def test_run_dashboard_binds_localhost_only_and_serves_the_build(tmp_path: Path) -> None:
    root = make_runner(tmp_path).project.root
    built_frontend(root)
    served, opened, built = {}, [], []

    def serve(app, **kwargs):
        served.update(kwargs, app=app)

    url = run_dashboard(root, port=8123, serve=serve, build=built.append,
                        opener=opened.append, open_browser=False)
    assert url == "http://127.0.0.1:8123/"
    assert served["host"] == "127.0.0.1" and served["port"] == 8123
    assert built == []  # the build is newer than the inputs
    client = TestClient(served["app"], base_url="http://127.0.0.1:8123")
    page = client.get("/")
    assert page.status_code == 200 and "<title>dash</title>" in page.text
    assert client.get("/api/meta").json()["project"] == "statarb-agent"
    missing = client.get("/api/nothing-here")
    assert missing.status_code == 404 and missing.json()["error"] == "not_found"


def test_run_dashboard_builds_when_out_of_date(tmp_path: Path) -> None:
    root = make_runner(tmp_path).project.root
    frontend = built_frontend(root)
    (frontend / "src" / "main.tsx").write_text("changed")
    built = []
    run_dashboard(root, serve=lambda app, **kw: None, build=built.append, open_browser=False)
    assert built == [frontend]


def test_dev_mode_starts_vite_and_stops_it(tmp_path: Path) -> None:
    root = make_runner(tmp_path).project.root
    frontend = root / "frontend"
    with pytest.raises(DashboardError, match="npm ci"):
        run_dashboard(root, dev=True, serve=lambda app, **kw: None, open_browser=False)
    (frontend / "node_modules").mkdir(parents=True)
    started = []

    class Vite:
        terminated = False

        def terminate(self) -> None:
            Vite.terminated = True

    def popen(cmd, **kwargs):
        started.append((cmd, kwargs["cwd"]))
        return Vite()

    served = {}
    url = run_dashboard(root, dev=True, popen=popen, open_browser=False,
                        serve=lambda app, **kw: served.update(kw, app=app))
    assert url == "http://127.0.0.1:5173/"
    assert started == [(["npm", "run", "dev"], frontend)] and Vite.terminated
    assert served["host"] == "127.0.0.1"
    # the Vite proxy keeps its own Host header, which dev mode accepts
    client = TestClient(served["app"], base_url="http://127.0.0.1:5173")
    assert client.get("/api/meta").status_code == 200


def test_static_files_get_the_same_local_only_checks_and_headers(tmp_path: Path) -> None:
    root = make_runner(tmp_path).project.root
    frontend = built_frontend(root)
    app = create_app(root, static_dir=frontend / "dist")
    client = TestClient(app, base_url=BASE)
    page = client.get("/")
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/meta").headers["cache-control"] == "no-store"
    foreign = TestClient(app, base_url="http://evil.example:8000")
    assert foreign.get("/").status_code == 403
    with pytest.raises(FileNotFoundError, match="build the frontend"):
        create_app(root, static_dir=tmp_path / "empty")


def test_cli_dashboard_passes_its_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_runner(tmp_path).project.root
    seen = {}
    monkeypatch.setattr(server, "run_dashboard", lambda r, **kw: seen.update(kw, root=r))
    result = CliRunner().invoke(
        cli.app, ["--root", str(root), "dashboard", "--port", "8200", "--no-open"]
    )
    assert result.exit_code == 0, result.output
    assert seen == {"root": root, "port": 8200, "dev": False, "open_browser": False}

    def fail(r, **kw):
        raise DashboardError("frontend packages are not installed; run `npm ci`")

    monkeypatch.setattr(server, "run_dashboard", fail)
    result = CliRunner().invoke(cli.app, ["--root", str(root), "dashboard", "--no-open"])
    assert result.exit_code != 0 and "npm ci" in result.output
