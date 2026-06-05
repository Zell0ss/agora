from backend.db.connection import get_db


async def get_channel(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        return await cur.fetchone()


async def get_active_roster(channel_id: int) -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.*, cp.speaking_order
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s
              AND cp.active = TRUE
              AND p.archived = FALSE
            ORDER BY cp.speaking_order
            """,
            (channel_id,),
        )
        return await cur.fetchall()
