from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kairos.api.routes import router
from kairos.config import Settings, get_settings
from kairos.db import connect, init_db
from kairos.services.scheduler import build_scheduler

DEFAULT_STATIC = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None, static_dir: Path | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(settings.db_path)
        init_db(conn, settings)
        conn.close()
        sched = None
        if settings.scheduler_enabled:
            sched = build_scheduler(settings)
            sched.start()
        yield
        if sched:
            sched.shutdown(wait=False)

    app = FastAPI(title="Kairos", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(router)
    _mount_frontend(app, static_dir or DEFAULT_STATIC)
    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built React app; unknown non-API paths fall back to index.html."""
    index = static_dir / "index.html"
    if not index.exists():
        return
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)
