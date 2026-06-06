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


async def get_total_cost_usd(channel_id: int) -> Decimal:
    async with get_db() as cur:
        await cur.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM messages WHERE channel_id = %s",
            (channel_id,),
        )
        row = await cur.fetchone()
        return Decimal(str(row["total"]))


async def count_messages_after(channel_id: int, after_msg_id: int | None) -> int:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE channel_id = %s AND id > %s",
                (channel_id, after_msg_id),
            )
        else:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE channel_id = %s",
                (channel_id,),
            )
        row = await cur.fetchone()
        return int(row["cnt"])


async def get_messages_chunk(
    channel_id: int, after_msg_id: int | None, limit: int
) -> list[dict]:
    async with get_db() as cur:
        if after_msg_id is not None:
            await cur.execute(
                """
                SELECT m.id, m.role, m.profile_id, m.content, p.name AS profile_name
                FROM messages m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.channel_id = %s AND m.id > %s
                ORDER BY m.id ASC
                LIMIT %s
                """,
                (channel_id, after_msg_id, limit),
            )
        else:
            await cur.execute(
                """
                SELECT m.id, m.role, m.profile_id, m.content, p.name AS profile_name
                FROM messages m
                LEFT JOIN profiles p ON m.profile_id = p.id
                WHERE m.channel_id = %s
                ORDER BY m.id ASC
                LIMIT %s
                """,
                (channel_id, limit),
            )
        return await cur.fetchall()


async def get_last_human_message(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT * FROM messages
            WHERE channel_id = %s AND role = 'human'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (channel_id,),
        )
        return await cur.fetchone()


async def insert_summary(
    channel_id: int, content: str, covers_up_to_msg_id: int
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO summaries (channel_id, content, covers_up_to_msg_id)
            VALUES (%s, %s, %s)
            """,
            (channel_id, content, covers_up_to_msg_id),
        )
        return cur.lastrowid
