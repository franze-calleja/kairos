from fastapi import FastAPI

from kairos.api.routes import router
from kairos.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Kairos")
    app.state.settings = settings
    app.include_router(router)
    return app
