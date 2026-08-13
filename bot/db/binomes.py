import aiosqlite


async def get_partner_id(
    db: aiosqlite.Connection, member_id: int, wave_id: int, semaine: int
) -> int | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """SELECT membre_a, membre_b FROM binomes
           WHERE wave_id = ? AND semaine = ? AND (membre_a = ? OR membre_b = ?)""",
        (wave_id, semaine, member_id, member_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return row["membre_b"] if row["membre_a"] == member_id else row["membre_a"]


async def list_binomes_semaine(
    db: aiosqlite.Connection, wave_id: int, semaine: int
) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """SELECT binomes.*, ma.nom AS nom_a, mb.nom AS nom_b
           FROM binomes
           JOIN members ma ON ma.id = binomes.membre_a
           JOIN members mb ON mb.id = binomes.membre_b
           WHERE binomes.wave_id = ? AND binomes.semaine = ?
           ORDER BY ma.nom""",
        (wave_id, semaine),
    ) as cur:
        return await cur.fetchall()


async def define_binome(
    db: aiosqlite.Connection, wave_id: int, semaine: int, membre_a: int, membre_b: int
) -> None:
    await db.execute(
        "INSERT INTO binomes (wave_id, semaine, membre_a, membre_b) VALUES (?, ?, ?, ?)",
        (wave_id, semaine, membre_a, membre_b),
    )
    await db.commit()
