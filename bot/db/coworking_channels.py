import aiosqlite


async def is_coworking_channel(db: aiosqlite.Connection, canal_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM coworking_channels WHERE canal_id = ? AND actif = 1", (canal_id,)
    ) as cur:
        return (await cur.fetchone()) is not None


async def add_channel(db: aiosqlite.Connection, canal_id: str, canal_nom: str) -> None:
    await db.execute(
        "INSERT INTO coworking_channels (canal_id, canal_nom, actif) VALUES (?, ?, 1) "
        "ON CONFLICT(canal_id) DO UPDATE SET actif = 1, canal_nom = excluded.canal_nom",
        (canal_id, canal_nom),
    )
    await db.commit()


async def remove_channel(db: aiosqlite.Connection, canal_id: str) -> None:
    await db.execute("UPDATE coworking_channels SET actif = 0 WHERE canal_id = ?", (canal_id,))
    await db.commit()
