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


async def define_binome(
    db: aiosqlite.Connection, wave_id: int, semaine: int, membre_a: int, membre_b: int
) -> None:
    await db.execute(
        "INSERT INTO binomes (wave_id, semaine, membre_a, membre_b) VALUES (?, ?, ?, ?)",
        (wave_id, semaine, membre_a, membre_b),
    )
    await db.commit()
