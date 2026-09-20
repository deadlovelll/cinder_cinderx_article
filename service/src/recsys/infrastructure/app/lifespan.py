from contextlib import asynccontextmanager

from fastapi import FastAPI

from recsys.infrastructure.app.shutdown import shutdown
from recsys.infrastructure.app.startup import startup


@asynccontextmanager
async def lifespan(application: FastAPI):
    await startup(application)
    try:
        yield
    finally:
        await shutdown(application)
