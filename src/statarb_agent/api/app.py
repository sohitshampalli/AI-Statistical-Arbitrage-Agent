"""The dashboard's FastAPI application.

`create_app(root)` builds the app over one project folder. Every reading
endpoint is a GET that returns a pydantic model from api.schemas. Errors are
always an ErrorBody: a plain message with the endpoint and the run id.

Local-only safety, each covered by a test:
- The server is meant to bind 127.0.0.1 (the CLI does that). On top of that,
  a request whose Host header is not this computer's address and port is
  refused, so a web page on another site cannot reach the API through DNS
  rebinding.
- A request carrying a foreign Origin header is refused, so another site's
  page open in the same browser cannot read or post to the API.
- No endpoint places orders, and none can touch the test period: the store
  only reads, and the study lock is enforced by the library underneath.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml
from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from statarb_agent.api import schemas as s
from statarb_agent.api.series import span_series
from statarb_agent.api.store import ResultStore
from statarb_agent.backtest.runner import counts_for_deflation
from statarb_agent.backtest.runs import RunError
from statarb_agent.provenance import code_version
from statarb_agent.study import is_test_period_unlocked, load_study

DEFAULT_PORT: Final = 8000
DEV_PORT: Final = 5173
GATES_PATH: Final = Path("docs") / "gates.yaml"
SPANS: Final = ("full", "formation", "validation")
MAX_PAGE: Final = 500
COUNTING_RULE: Final = (
    "Counted for the Deflated Sharpe ratio: every real-data backtest with "
    "outcome ok (each hedge and cost level is its own trial, placebo and "
    "control batches excluded), plus one attempt for every real candidate "
    "that was analysed and never backtested."
)


class ApiError(Exception):
    """An error returned as an ErrorBody with an HTTP status."""

    def __init__(
        self, status: int, error: str, message: str, run_id: str | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.run_id = run_id


def allowed_hosts(port: int, *, dev: bool = False) -> frozenset[str]:
    # In dev mode the Vite server proxies /api and keeps its own Host header.
    ports = [port, DEV_PORT] if dev else [port]
    return frozenset(f"{host}:{p}" for p in ports for host in ("127.0.0.1", "localhost"))


def allowed_origins(port: int, *, dev: bool) -> frozenset[str]:
    ports = [port, DEV_PORT] if dev else [port]
    return frozenset(
        f"http://{host}:{p}" for p in ports for host in ("127.0.0.1", "localhost")
    )


class LocalOnlyMiddleware:
    """Refuse requests whose Host or Origin is not this local server."""

    def __init__(
        self, app: ASGIApp, *, hosts: frozenset[str], origins: frozenset[str]
    ) -> None:
        self.app = app
        self.hosts = hosts
        self.origins = origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        host = headers.get("host")
        origin = headers.get("origin")
        if host not in self.hosts:
            problem = f"host {host!r} is not this local dashboard"
        elif origin is not None and origin not in self.origins:
            problem = f"origin {origin!r} is not this local dashboard"
        else:
            await self.app(scope, receive, send)
            return
        body = s.ErrorBody(error="forbidden", message=problem, endpoint=scope["path"])
        response = JSONResponse(body.model_dump(), status_code=403)
        await response(scope, receive, send)


SECURITY_HEADERS: Final = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
)


class SecurityHeadersMiddleware:
    """Add headers that stop framing, sniffing, referrers and caching."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []),
                                                  *SECURITY_HEADERS]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


# Conversions --------------------------------------------------------------


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date().isoformat()
    if value is pd.NaT:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _iso(value: Any) -> str | int:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return _cell(value)


def table_payload(
    run_id: str, name: str, sha256: str, frame: pd.DataFrame
) -> s.Table:
    """A stored table as columns of plain JSON values."""
    columns = {}
    for column in frame.columns:
        series = frame[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            values = [None if pd.isna(v) else v.date().isoformat() for v in series]
        else:
            values = [_cell(v) for v in series.to_numpy(dtype=object)]
        columns[str(column)] = values
    return s.Table(
        run_id=run_id, name=name, sha256=sha256, index_name=frame.index.name,
        index=[_iso(v) for v in frame.index], columns=columns,
    )


def _floats(values: Any) -> list[float | None]:
    return [None if not math.isfinite(v) else float(v) for v in values]


# Application --------------------------------------------------------------


def create_app(
    root: Path, *, port: int = DEFAULT_PORT, dev: bool = False,
    static_dir: Path | None = None,
) -> FastAPI:
    """The dashboard API over the project folder `root`.

    With `static_dir` (the built frontend, frontend/dist) the app also serves
    the dashboard itself at /. API routes take precedence.
    """
    root = Path(root)
    store = ResultStore(root)
    app = FastAPI(
        title="statarb-agent dashboard", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        LocalOnlyMiddleware, hosts=allowed_hosts(port, dev=dev),
        origins=allowed_origins(port, dev=dev),
    )
    app.state.store = store
    app.state.root = root

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        body = s.ErrorBody(
            error=exc.error, message=exc.message, endpoint=request.url.path,
            run_id=exc.run_id,
        )
        return JSONResponse(body.model_dump(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _bad_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        body = s.ErrorBody(error="bad_request", message=problems, endpoint=request.url.path)
        return JSONResponse(body.model_dump(), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        body = s.ErrorBody(
            error="not_found" if exc.status_code == 404 else "http_error",
            message=str(exc.detail), endpoint=request.url.path,
        )
        return JSONResponse(body.model_dump(), status_code=exc.status_code)

    app.include_router(build_router(store, root))
    if static_dir is not None:
        if not (Path(static_dir) / "index.html").is_file():
            raise FileNotFoundError(f"{static_dir} has no index.html; build the frontend")
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


def _head(root: Path) -> tuple[str, bool]:
    version = code_version(root)
    return version.commit, version.dirty


def _manifest(store: ResultStore, run_id: str, head: str) -> s.RunManifest:
    try:
        raw = store.run(run_id)
    except ValueError as exc:
        raise ApiError(400, "bad_run_id", str(exc), run_id=None) from exc
    except RunError as exc:
        if not (store.project.runs_dir / run_id).is_dir():
            raise ApiError(404, "not_found", f"no run {run_id}", run_id) from exc
        raise ApiError(500, "integrity", str(exc), run_id) from exc
    stale = raw.get("provenance", {}).get("code_commit") != head
    try:
        return s.RunManifest.model_validate({**raw, "stale": stale})
    except ValidationError as exc:
        raise ApiError(
            500, "schema", f"run.json does not fit the API schema: {exc}", run_id
        ) from exc


def build_router(store: ResultStore, root: Path) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/meta", response_model=s.Meta)
    def meta() -> s.Meta:
        commit, dirty = _head(root)
        study = load_study(store.project.study_path)
        stats = store.trial_stats()
        latest = store.latest_summary()
        present = [x for x in store.snapshots() if x["file_present"]]
        firsts = [x["first_date"][:10] for x in present if x["first_date"]]
        lasts = [x["last_date"][:10] for x in present if x["last_date"]]
        sources = store.sources()
        summary_counted = None if latest is None else latest.get("n_trials_counted")
        return s.Meta(
            project="statarb-agent",
            head_commit=commit,
            head_dirty=dirty,
            study=s.StudyPeriods(
                formation_start=study.formation.start.date().isoformat(),
                formation_end=study.formation.end.date().isoformat(),
                validation_start=study.validation.start.date().isoformat(),
                validation_end=study.validation.end.date().isoformat(),
                test_start=study.test_start.date().isoformat(),
                test_period_locked=not is_test_period_unlocked(study, root),
            ),
            trials_in_log=stats["n_lines"],
            trials_counted=stats["n_counted"],
            latest_summary_id=None if latest is None else latest["run_id"],
            latest_summary_trials_counted=summary_counted,
            summary_stale=summary_counted is not None
            and summary_counted != stats["n_counted"],
            data_first_date=min(firsts) if firsts else None,
            data_last_date=max(lasts) if lasts else None,
            downloads_enabled=any(x.downloads_enabled for x in sources),
            paper_trading_only=True,
        )

    @router.get("/runs", response_model=s.RunList)
    def runs(
        kind: str | None = None, label: str | None = None, ticker: str | None = None,
        hedge: str | None = None, cost_bps: float | None = None,
    ) -> s.RunList:
        head, _ = _head(root)
        items = []
        for r in store.runs():
            if kind is not None and r["kind"] != kind:
                continue
            if label is not None and r["label"] != label:
                continue
            if ticker is not None and ticker.upper() not in (r["tickers"] or []):
                continue
            if hedge is not None and r["hedge"] != hedge:
                continue
            if cost_bps is not None and r["cost_bps"] != cost_bps:
                continue
            items.append(s.RunListItem(**r, stale=r["code_commit"] != head))
        return s.RunList(runs=items)

    @router.get("/runs/{run_id}", response_model=s.RunManifest)
    def run(run_id: str) -> s.RunManifest:
        head, _ = _head(root)
        return _manifest(store, run_id, head)

    @router.get("/runs/{run_id}/tables/{name}", response_model=s.Table)
    def table(
        run_id: str, name: str,
        columns: str | None = Query(None, description="comma-separated column names"),
        start: str | None = None, end: str | None = None,
    ) -> s.Table:
        head, _ = _head(root)
        manifest = _manifest(store, run_id, head)
        entry = manifest.files.get(name)
        if entry is None:
            raise ApiError(404, "not_found", f"run {run_id} has no table {name!r}", run_id)
        try:
            frame = store.table(run_id, name)
        except RunError as exc:
            raise ApiError(500, "integrity", str(exc), run_id) from exc
        if columns:
            wanted = [c for c in columns.split(",") if c]
            unknown = [c for c in wanted if c not in frame.columns]
            if unknown:
                raise ApiError(400, "bad_request", f"unknown columns {unknown}", run_id)
            frame = frame[wanted]
        if start or end:
            if not isinstance(frame.index, pd.DatetimeIndex):
                raise ApiError(
                    400, "bad_request", f"table {name!r} is not indexed by date", run_id
                )
            try:
                lo = pd.Timestamp(start) if start else frame.index.min()
                hi = pd.Timestamp(end) if end else frame.index.max()
            except ValueError as exc:
                raise ApiError(400, "bad_request", f"bad date: {exc}", run_id) from exc
            frame = frame.loc[(frame.index >= lo) & (frame.index <= hi)]
        return table_payload(run_id, name, entry.sha256, frame)

    @router.get("/runs/{run_id}/series/equity", response_model=s.EquitySeries)
    def equity(run_id: str, span: str = "validation") -> s.EquitySeries:
        head, _ = _head(root)
        manifest = _manifest(store, run_id, head)
        if span not in SPANS:
            raise ApiError(400, "bad_request", f"span must be one of {SPANS}", run_id)
        if manifest.kind != "backtest" or manifest.metrics is None:
            raise ApiError(400, "bad_request", "only backtest runs have equity", run_id)
        metrics = manifest.metrics.get(span)
        if metrics is None:
            raise ApiError(404, "not_found", f"run has no {span} span", run_id)
        try:
            daily = store.table(run_id, "daily")
        except RunError as exc:
            raise ApiError(500, "integrity", str(exc), run_id) from exc
        series = span_series(daily, metrics.start, metrics.end)
        return s.EquitySeries(
            run_id=run_id, span=span, start=metrics.start, end=metrics.end,
            cost_bps=manifest.cost_bps,
            dates=[d.date().isoformat() for d in series.dates],
            equity=_floats(series.equity), gross_equity=_floats(series.gross_equity),
            drawdown=_floats(series.drawdown),
            stored_max_drawdown=metrics.max_drawdown,
            stored_total_return=metrics.total_return,
            provenance=manifest.provenance,
        )

    @router.get("/compare", response_model=s.RunCompare)
    def compare(a: str, b: str) -> s.RunCompare:
        head, _ = _head(root)
        return s.RunCompare(a=_manifest(store, a, head), b=_manifest(store, b, head))

    @router.get("/summary/latest", response_model=s.RunManifest)
    def latest_summary() -> s.RunManifest:
        latest = store.latest_summary()
        if latest is None:
            raise ApiError(
                404, "not_found",
                "no summary stored yet; `uv run statarb summarise` writes one",
            )
        head, _ = _head(root)
        return _manifest(store, latest["run_id"], head)

    @router.get("/trials", response_model=s.TrialPage)
    def trials(
        kind: str | None = None, label: str | None = None,
        outcome: str | None = None, ticker: str | None = None,
        offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=MAX_PAGE),
    ) -> s.TrialPage:
        rows = []
        for line, t in enumerate(store.trials(), start=1):
            if kind is not None and t.kind != kind:
                continue
            if label is not None and t.label != label:
                continue
            if outcome is not None and t.outcome != outcome:
                continue
            if ticker is not None and ticker.upper() not in t.tickers:
                continue
            rows.append((line, t))
        items = [
            s.TrialItem(
                line=line, **{**t.to_json(), "tickers": list(t.tickers)},
                counted=counts_for_deflation(t),
            )
            for line, t in rows[offset: offset + limit]
        ]
        return s.TrialPage(total=len(rows), offset=offset, limit=limit, items=items)

    @router.get("/trials/stats", response_model=s.TrialStats)
    def trial_stats() -> s.TrialStats:
        return s.TrialStats(**store.trial_stats(), counting_rule=COUNTING_RULE)

    @router.get("/pairs", response_model=s.Pairs)
    def pairs() -> s.Pairs:
        return s.Pairs.model_validate(store.pairs())

    @router.get("/configs", response_model=s.Configs)
    def configs() -> s.Configs:
        return s.Configs(configs=[s.ConfigFile(**c) for c in store.configs()])

    @router.get("/gates", response_model=s.Gates)
    def gates() -> s.Gates:
        path = root / GATES_PATH
        if not path.is_file():
            raise ApiError(404, "not_found", f"{GATES_PATH} is missing")
        return s.Gates.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    @router.get("/data", response_model=s.DataProvenance)
    def data() -> s.DataProvenance:
        return s.DataProvenance(
            sources=[s.SourceInfoModel(**vars(x)) for x in store.sources()],
            snapshots=[s.Snapshot(**x) for x in store.snapshots()],
            cached_tickers=store.cached_tickers(),
        )

    return router
