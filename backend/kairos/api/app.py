from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kairos.api.routes import router
from kairos.config import Settings, get_settings
from kairos.db import connect, init_db
from kairos.services.scheduler import build_scheduler


def create_app(settings: Settings | None = None) -> FastAPI:
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
    app.state.job_running = False
    app.include_router(router)
    return app
