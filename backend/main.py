from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.channels import router as channels_router
from backend.api.profiles import router as profiles_router
from backend.api.stream import router as stream_router
from backend.api.synthesize import router as synthesize_router
from backend.db.connection import close_pool, init_pool
from backend.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    logger.info("startup: DB pool initialized")
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
app.include_router(synthesize_router)
app.include_router(profiles_router)
app.include_router(channels_router)
