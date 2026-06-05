from contextlib import asynccontextmanager

import aiomysql

from backend.config import settings

_pool: aiomysql.Pool | None = None


async def init_pool() -> None:
    global _pool
    _pool = await aiomysql.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        db=settings.db_name,
        autocommit=True,  # single-statement writes only in Fase 1; no multi-statement tx support
        charset="utf8mb4",
        minsize=1,
        maxsize=10,
    )


async def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


@asynccontextmanager
async def get_db():
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() first")
    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            yield cur
