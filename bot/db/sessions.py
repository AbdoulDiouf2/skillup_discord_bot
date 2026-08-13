from datetime import date, datetime

import aiosqlite


async def get_open_session(db: aiosqlite.Connection, member_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM sessions WHERE member_id = ? AND fin IS NULL", (member_id,)
    ) as cur:
        return await cur.fetchone()


async def start_session(
    db: aiosqlite.Connection,
    member_id: int,
    wave_id: int,
    semaine: int,
    session_date: date,
    creneau: str,
    canal_id: str | None,
    canal_nom: str | None,
    debut: datetime,
    objectif: str,
) -> int:
    cur = await db.execute(
        """INSERT INTO sessions
           (member_id, wave_id, semaine, date, creneau, canal_id, canal_nom, debut, objectif, statut)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ouverte')""",
        (
            member_id,
            wave_id,
            semaine,
            session_date.isoformat(),
            creneau,
            canal_id,
            canal_nom,
            debut.isoformat(),
            objectif,
        ),
    )
    await db.commit()
    return cur.lastrowid


async def end_session(
    db: aiosqlite.Connection,
    session_id: int,
    fin: datetime,
    bilan: str,
    blocages: str | None,
) -> None:
    await db.execute(
        """UPDATE sessions SET fin = ?, bilan = ?, blocages = ?, statut = 'complète'
           WHERE id = ?""",
        (fin.isoformat(), bilan, blocages, session_id),
    )
    await db.commit()


async def list_recent_by_member(
    db: aiosqlite.Connection, member_id: int, limit: int = 25
) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM sessions WHERE member_id = ? ORDER BY debut DESC LIMIT ?",
        (member_id, limit),
    ) as cur:
        return await cur.fetchall()


async def get_by_id(db: aiosqlite.Connection, session_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cur:
        return await cur.fetchone()


async def update_field(db: aiosqlite.Connection, session_id: int, champ: str, valeur: str) -> None:
    await db.execute(f"UPDATE sessions SET {champ} = ? WHERE id = ?", (valeur, session_id))
    await db.commit()


async def delete_session(db: aiosqlite.Connection, session_id: int) -> None:
    await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await db.commit()


async def list_by_member_week(
    db: aiosqlite.Connection, member_id: int, wave_id: int, semaine: int
) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """SELECT * FROM sessions WHERE member_id = ? AND wave_id = ? AND semaine = ?
           ORDER BY debut ASC""",
        (member_id, wave_id, semaine),
    ) as cur:
        return await cur.fetchall()
