from decimal import Decimal

from backend.db.connection import get_db


async def insert_message(
    channel_id: int,
    role: str,
    content: str,
    profile_id: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: Decimal | None = None,
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO messages
              (channel_id, role, profile_id, content, tokens_in, tokens_out, cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (channel_id, role, profile_id, content, tokens_in, tokens_out, cost_usd),
        )
        return cur.lastrowid


async def get_context_messages(
    channel_id: int,
    after_msg_id: int | None = None,
) -> list[dict]:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                """
                SELECT * FROM messages
                WHERE channel_id = %s AND id > %s
                ORDER BY created_at
                """,
                (channel_id, after_msg_id),
            )
        else:
            await cur.execute(
                "SELECT * FROM messages WHERE channel_id = %s ORDER BY created_at",
                (channel_id,),
            )
        return await cur.fetchall()


async def get_latest_summary(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT * FROM summaries
            WHERE channel_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (channel_id,),
        )
        return await cur.fetchone()
