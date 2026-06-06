from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.channels import router as channels_router
from backend.api.profiles import router as profiles_router
from backend.api.stream import router as stream_router
from backend.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Agora API", version="0.1.0", lifespan=lifespan)
app.include_router(stream_router)
app.include_router(profiles_router)
app.include_router(channels_router)
