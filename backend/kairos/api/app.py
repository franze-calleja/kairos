from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kairos.api.routes import router
from kairos.config import Settings, get_settings
from kairos.db import connect, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(settings.db_path)
        init_db(conn, settings)
        conn.close()
        yield

    app = FastAPI(title="Kairos", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(router)
    return app
