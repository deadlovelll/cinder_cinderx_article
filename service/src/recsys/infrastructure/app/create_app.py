from fastapi import FastAPI

from recsys.infrastructure.app.error_handlers import install_error_handlers
from recsys.infrastructure.app.lifespan import lifespan
from recsys.infrastructure.bootstrap.runtime_report import BOOTSTRAP


def create_app() -> FastAPI:
    application = FastAPI(
        title="recsys",
        version="1.0.0",
        summary="A recommendation service, used as the workload for measuring CinderX.",
        lifespan=lifespan,
    )
    install_error_handlers(application)
    from recsys.api.routes import bundle, health, recommend, similar

    for module in (recommend, similar, bundle, health):
        application.include_router(module.router)
    application.state.bootstrap = BOOTSTRAP
    return application
