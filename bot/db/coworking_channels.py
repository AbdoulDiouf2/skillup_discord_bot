import aiosqlite


async def is_coworking_channel(db: aiosqlite.Connection, canal_id: str, wave_id: int) -> bool:
    async with db.execute(
        "SELECT 1 FROM coworking_channels WHERE canal_id = ? AND wave_id = ? AND actif = TRUE",
        (canal_id, wave_id),
    ) as cur:
        return (await cur.fetchone()) is not None


async def add_channel(db: aiosqlite.Connection, canal_id: str, canal_nom: str, wave_id: int) -> None:
    await db.execute(
        "INSERT INTO coworking_channels (canal_id, canal_nom, actif, wave_id) VALUES (?, ?, TRUE, ?) "
        "ON CONFLICT (canal_id, wave_id) DO UPDATE SET actif = TRUE, canal_nom = excluded.canal_nom",
        (canal_id, canal_nom, wave_id),
    )
    await db.commit()


async def remove_channel(db: aiosqlite.Connection, canal_id: str, wave_id: int) -> None:
    await db.execute(
        "UPDATE coworking_channels SET actif = FALSE WHERE canal_id = ? AND wave_id = ?",
        (canal_id, wave_id),
    )
    await db.commit()


async def list_channels(
    db: aiosqlite.Connection, wave_id: int | None = None, actif_seulement: bool = False
) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    clauses = []
    params: list = []
    if wave_id is not None:
        clauses.append("coworking_channels.wave_id = ?")
        params.append(wave_id)
    if actif_seulement:
        clauses.append("coworking_channels.actif = TRUE")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    async with db.execute(
        f"""SELECT coworking_channels.*, waves.nom AS wave_nom
            FROM coworking_channels
            JOIN waves ON waves.id = coworking_channels.wave_id
            {where}
            ORDER BY waves.date_debut DESC, coworking_channels.canal_nom""",
        params,
    ) as cur:
        return await cur.fetchall()
