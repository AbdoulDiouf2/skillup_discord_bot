import aiosqlite


async def get_ai_settings(db: aiosqlite.Connection) -> aiosqlite.Row:
    """Ligne unique (id=1), toujours présente (insérée par le schéma au démarrage)."""
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM ai_settings WHERE id = 1") as cur:
        return await cur.fetchone()


async def update_ai_settings(
    db: aiosqlite.Connection, enabled: bool, provider: str, model: str, updated_by: str, updated_at: str
) -> None:
    await db.execute(
        "UPDATE ai_settings SET enabled = ?, provider = ?, model = ?, "
        "updated_by_discord_id = ?, updated_at = ? WHERE id = 1",
        (enabled, provider, model, updated_by, updated_at),
    )
    await db.commit()
