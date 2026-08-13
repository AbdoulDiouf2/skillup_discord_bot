import aiosqlite


class BinomeError(Exception):
    pass


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
    for member_id in (membre_a, membre_b):
        partner_id = await get_partner_id(db, member_id, wave_id, semaine)
        if partner_id is not None:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT nom FROM members WHERE id = ?", (member_id,)
            ) as cur:
                membre_row = await cur.fetchone()
            async with db.execute(
                "SELECT nom FROM members WHERE id = ?", (partner_id,)
            ) as cur:
                partenaire_row = await cur.fetchone()
            raise BinomeError(
                f"{membre_row['nom']} est déjà associé à {partenaire_row['nom']} cette semaine — "
                f"utilise `/binome-retirer` d'abord."
            )

    cur = await db.execute(
        "INSERT INTO binomes (wave_id, semaine, membre_a, membre_b) VALUES (?, ?, ?, ?)",
        (wave_id, semaine, membre_a, membre_b),
    )
    binome_id = cur.lastrowid
    await db.execute(
        "INSERT INTO binome_membres (binome_id, member_id, wave_id, semaine) VALUES (?, ?, ?, ?)",
        (binome_id, membre_a, wave_id, semaine),
    )
    await db.execute(
        "INSERT INTO binome_membres (binome_id, member_id, wave_id, semaine) VALUES (?, ?, ?, ?)",
        (binome_id, membre_b, wave_id, semaine),
    )
    await db.commit()


async def remove_binome(
    db: aiosqlite.Connection, wave_id: int, semaine: int, member_id: int
) -> bool:
    """Dissout le binôme contenant ce membre pour cette (vague, semaine). Retourne
    False si le membre n'était dans aucun binôme."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """SELECT id FROM binomes
           WHERE wave_id = ? AND semaine = ? AND (membre_a = ? OR membre_b = ?)""",
        (wave_id, semaine, member_id, member_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return False

    binome_id = row["id"]
    await db.execute("DELETE FROM binome_membres WHERE binome_id = ?", (binome_id,))
    await db.execute("DELETE FROM binomes WHERE id = ?", (binome_id,))
    await db.commit()
    return True
