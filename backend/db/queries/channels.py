from backend.db.connection import get_db


async def get_channel(channel_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
        return await cur.fetchone()


async def list_channels() -> list[dict]:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM channels ORDER BY id")
        return await cur.fetchall()


async def insert_channel(title: str, mode: str, incognito: bool) -> int:
    async with get_db() as cur:
        await cur.execute(
            "INSERT INTO channels (title, mode, incognito) VALUES (%s, %s, %s)",
            (title, mode, incognito),
        )
        return cur.lastrowid


async def update_channel(channel_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [channel_id]
    async with get_db() as cur:
        await cur.execute(f"UPDATE channels SET {set_clause} WHERE id = %s", values)


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


async def get_full_roster(channel_id: int) -> list[dict]:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.id AS profile_id, p.name, p.tipo, cp.speaking_order, cp.active
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s AND cp.active = TRUE
            ORDER BY cp.speaking_order
            """,
            (channel_id,),
        )
        return await cur.fetchall()


async def get_roster_entry(channel_id: int, profile_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            """
            SELECT p.id AS profile_id, p.name, p.tipo, cp.speaking_order, cp.active
            FROM channel_profiles cp
            JOIN profiles p ON p.id = cp.profile_id
            WHERE cp.channel_id = %s AND cp.profile_id = %s
            """,
            (channel_id, profile_id),
        )
        return await cur.fetchone()


async def count_active_roster(channel_id: int) -> int:
    async with get_db() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM channel_profiles WHERE channel_id = %s AND active = TRUE",
            (channel_id,),
        )
        row = await cur.fetchone()
        return row["cnt"]


async def add_to_roster(channel_id: int, profile_id: int, speaking_order: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO channel_profiles (channel_id, profile_id, speaking_order)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE active = TRUE, speaking_order = %s
            """,
            (channel_id, profile_id, speaking_order, speaking_order),
        )


async def remove_from_roster(channel_id: int, profile_id: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            "UPDATE channel_profiles SET active = FALSE WHERE channel_id = %s AND profile_id = %s",
            (channel_id, profile_id),
        )


async def update_roster_entry(channel_id: int, profile_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [channel_id, profile_id]
    async with get_db() as cur:
        await cur.execute(
            f"UPDATE channel_profiles SET {set_clause} WHERE channel_id = %s AND profile_id = %s",
            values,
        )
