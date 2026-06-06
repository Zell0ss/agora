from backend.db.connection import get_db


async def get_profile(profile_id: int) -> dict | None:
    async with get_db() as cur:
        await cur.execute(
            "SELECT * FROM profiles WHERE id = %s AND archived = FALSE", (profile_id,)
        )
        return await cur.fetchone()


async def list_profiles() -> list[dict]:
    async with get_db() as cur:
        await cur.execute("SELECT * FROM profiles WHERE archived = FALSE ORDER BY id")
        return await cur.fetchall()


async def insert_profile(
    name: str,
    tipo: str,
    model: str,
    temperature: float,
    color: str | None,
    funcion: str,
    system_prompt: str,
) -> int:
    async with get_db() as cur:
        await cur.execute(
            """
            INSERT INTO profiles (name, tipo, model, temperature, color, funcion, system_prompt)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (name, tipo, model, temperature, color, funcion, system_prompt),
        )
        return cur.lastrowid


async def update_profile(profile_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [profile_id]
    async with get_db() as cur:
        await cur.execute(f"UPDATE profiles SET {set_clause} WHERE id = %s", values)


async def get_moderador_profile() -> dict | None:
    """Find the Moderador utility profile (by funcion keyword)."""
    async with get_db() as cur:
        await cur.execute(
            "SELECT * FROM profiles WHERE LOWER(funcion) LIKE '%moderador%' AND archived = FALSE LIMIT 1"
        )
        return await cur.fetchone()


async def archive_profile(profile_id: int) -> None:
    async with get_db() as cur:
        await cur.execute(
            "UPDATE profiles SET archived = TRUE WHERE id = %s", (profile_id,)
        )
