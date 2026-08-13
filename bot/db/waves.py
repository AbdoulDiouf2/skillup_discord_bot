from datetime import date

import aiosqlite


async def get_active_wave(db: aiosqlite.Connection) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM waves WHERE active = 1 LIMIT 1") as cur:
        return await cur.fetchone()


async def create_wave(db: aiosqlite.Connection, nom: str, date_debut: date, date_fin: date) -> int:
    await db.execute("UPDATE waves SET active = 0 WHERE active = 1")
    cur = await db.execute(
        "INSERT INTO waves (nom, date_debut, date_fin, active) VALUES (?, ?, ?, 1)",
        (nom, date_debut.isoformat(), date_fin.isoformat()),
    )
    await db.commit()
    return cur.lastrowid
