"""Start the dashboard: build the frontend if needed, serve it on localhost.

`statarb dashboard` calls `run_dashboard`. The server always binds 127.0.0.1,
never a public address. With dev=True the Vite dev server runs as well (hot
reload on http://127.0.0.1:5173, proxying /api to this server).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import webbrowser
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

from statarb_agent.api.app import DEFAULT_PORT, DEV_PORT, create_app

HOST: Final = "127.0.0.1"
FRONTEND_DIR: Final = Path("frontend")
# Files whose change means the built dashboard is out of date.
BUILD_INPUTS: Final = (
    "src", "index.html", "package.json", "package-lock.json", "vite.config.ts",
    "tsconfig.json", "tsconfig.app.json",
)


class DashboardError(RuntimeError):
    """The dashboard cannot be started; the message says what to do."""


def _files(frontend: Path) -> Iterator[Path]:
    for name in BUILD_INPUTS:
        path = frontend / name
        if path.is_dir():
            yield from (p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            yield path


def needs_build(frontend: Path) -> bool:
    """True if dist/index.html is missing or older than any build input."""
    built = frontend / "dist" / "index.html"
    if not built.is_file():
        return True
    stamp = built.stat().st_mtime
    return any(p.stat().st_mtime > stamp for p in _files(frontend))


def build_frontend(
    frontend: Path, *, run: Callable[..., Any] = subprocess.run
) -> None:
    """Run `npm run build` in frontend/.

    Raises:
        DashboardError: If npm or the installed packages are missing, or the
            build fails.
    """
    if shutil.which("npm") is None:
        raise DashboardError("npm is not installed; the dashboard frontend needs Node.js")
    if not (frontend / "node_modules").is_dir():
        raise DashboardError(
            f"frontend packages are not installed; run `npm ci` in {frontend}"
        )
    result = run(["npm", "run", "build"], cwd=frontend, check=False)
    if result.returncode != 0:
        raise DashboardError("the frontend build failed; see the output above")


def run_dashboard(
    root: Path,
    *,
    port: int = DEFAULT_PORT,
    dev: bool = False,
    open_browser: bool = True,
    serve: Callable[..., Any] | None = None,
    build: Callable[[Path], None] = build_frontend,
    popen: Callable[..., Any] = subprocess.Popen,
    opener: Callable[[str], Any] = webbrowser.open,
) -> str:
    """Build if needed, start the server on 127.0.0.1 and open the browser.

    Returns the URL the dashboard is served on. `serve`, `build`, `popen` and
    `opener` are replaceable for tests.
    """
    if serve is None:
        import uvicorn

        serve = uvicorn.run
    root = Path(root)
    frontend = root / FRONTEND_DIR
    vite = None
    if dev:
        if not (frontend / "node_modules").is_dir():
            raise DashboardError(
                f"frontend packages are not installed; run `npm ci` in {frontend}"
            )
        vite = popen(["npm", "run", "dev"], cwd=frontend)
        url = f"http://{HOST}:{DEV_PORT}/"
        app = create_app(root, port=port, dev=True)
    else:
        if needs_build(frontend):
            build(frontend)
        url = f"http://{HOST}:{port}/"
        app = create_app(root, port=port, static_dir=frontend / "dist")
    if open_browser:
        threading.Timer(1.5, opener, args=(url,)).start()
    try:
        serve(app, host=HOST, port=port, log_level="info")
    finally:
        if vite is not None:
            vite.terminate()
    return url
