import aiosqlite


async def get_member(db: aiosqlite.Connection, discord_id: str, wave_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM members WHERE discord_id = ? AND wave_id = ?", (discord_id, wave_id)
    ) as cur:
        return await cur.fetchone()


async def get_member_by_id(db: aiosqlite.Connection, member_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM members WHERE id = ?", (member_id,)) as cur:
        return await cur.fetchone()


async def update_objectif(db: aiosqlite.Connection, member_id: int, objectif: str) -> None:
    await db.execute(
        "UPDATE members SET objectif_vague = ? WHERE id = ?", (objectif, member_id)
    )
    await db.commit()


async def add_member(
    db: aiosqlite.Connection,
    discord_id: str,
    nom: str,
    profil: str,
    wave_id: int,
    certif_ou_projet: str | None = None,
) -> int:
    cur = await db.execute(
        "INSERT INTO members (discord_id, nom, profil, certif_ou_projet, wave_id) VALUES (?, ?, ?, ?, ?)",
        (discord_id, nom, profil, certif_ou_projet, wave_id),
    )
    await db.commit()
    return cur.lastrowid
