from datetime import date

import aiosqlite


class WaveError(Exception):
    pass


async def get_active_wave(db: aiosqlite.Connection) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM waves WHERE statut = 'active' LIMIT 1") as cur:
        return await cur.fetchone()


async def get_wave_by_id(db: aiosqlite.Connection, wave_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM waves WHERE id = ?", (wave_id,)) as cur:
        return await cur.fetchone()


async def list_waves(db: aiosqlite.Connection, statut: str | None = None) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    if statut:
        async with db.execute(
            "SELECT * FROM waves WHERE statut = ? ORDER BY date_debut DESC", (statut,)
        ) as cur:
            return await cur.fetchall()
    async with db.execute("SELECT * FROM waves ORDER BY date_debut DESC") as cur:
        return await cur.fetchall()


async def create_wave(db: aiosqlite.Connection, nom: str, date_debut: date, date_fin: date) -> int:
    """Crée une vague au statut brouillon — ne touche pas à la vague active existante."""
    cur = await db.execute(
        "INSERT INTO waves (nom, date_debut, date_fin, statut) VALUES (?, ?, ?, 'brouillon')",
        (nom, date_debut.isoformat(), date_fin.isoformat()),
    )
    await db.commit()
    return cur.lastrowid


async def activate_wave(db: aiosqlite.Connection, wave_id: int) -> aiosqlite.Row:
    wave = await get_wave_by_id(db, wave_id)
    if wave is None:
        raise WaveError("Vague introuvable.")
    if wave["statut"] != "brouillon":
        raise WaveError(f"La vague **{wave['nom']}** n'est pas en brouillon (statut actuel : {wave['statut']}).")

    existing_active = await get_active_wave(db)
    if existing_active is not None:
        raise WaveError(
            f"Une vague est déjà active (**{existing_active['nom']}**) — clôture-la d'abord avec `/vague-cloturer`."
        )

    await db.execute("UPDATE waves SET statut = 'active' WHERE id = ?", (wave_id,))
    await db.commit()
    return await get_wave_by_id(db, wave_id)


async def close_wave(db: aiosqlite.Connection, wave_id: int | None = None) -> aiosqlite.Row:
    if wave_id is None:
        wave = await get_active_wave(db)
        if wave is None:
            raise WaveError("Aucune vague active à clôturer.")
        wave_id = wave["id"]
    else:
        wave = await get_wave_by_id(db, wave_id)
        if wave is None:
            raise WaveError("Vague introuvable.")

    await db.execute("UPDATE waves SET statut = 'cloturee' WHERE id = ?", (wave_id,))
    await db.commit()
    return await get_wave_by_id(db, wave_id)


async def set_thread_bilan_collectif_id(db: aiosqlite.Connection, wave_id: int, thread_id: str) -> None:
    await db.execute("UPDATE waves SET thread_bilan_collectif_id = ? WHERE id = ?", (thread_id, wave_id))
    await db.commit()
