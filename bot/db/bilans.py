import aiosqlite


async def get_bilan_semaine(
    db: aiosqlite.Connection, member_id: int, wave_id: int, semaine: int
) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM bilans_semaine WHERE member_id = ? AND wave_id = ? AND semaine = ?",
        (member_id, wave_id, semaine),
    ) as cur:
        return await cur.fetchone()


async def upsert_bilan_semaine(
    db: aiosqlite.Connection,
    member_id: int,
    wave_id: int,
    semaine: int,
    texte: str,
    ecrit_par: str,
    updated_at: str,
) -> None:
    await db.execute(
        "INSERT INTO bilans_semaine (member_id, wave_id, semaine, texte, ecrit_par_discord_id, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (member_id, wave_id, semaine) DO UPDATE SET "
        "texte = excluded.texte, ecrit_par_discord_id = excluded.ecrit_par_discord_id, "
        "updated_at = excluded.updated_at",
        (member_id, wave_id, semaine, texte, ecrit_par, updated_at),
    )
    await db.commit()


async def list_bilans_semaine_by_wave(
    db: aiosqlite.Connection, wave_id: int, semaine: int
) -> list[aiosqlite.Row]:
    """Un rang par membre de la vague, bilan_texte/ecrit_par/updated_at NULL si le membre
    n'a pas encore de bilan hebdo rédigé pour cette semaine (LEFT JOIN)."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT members.discord_id, members.nom, "
        "bilans_semaine.texte, bilans_semaine.ecrit_par_discord_id, bilans_semaine.updated_at "
        "FROM members "
        "LEFT JOIN bilans_semaine ON bilans_semaine.member_id = members.id "
        "AND bilans_semaine.wave_id = members.wave_id AND bilans_semaine.semaine = ? "
        "WHERE members.wave_id = ? "
        "ORDER BY members.nom",
        (semaine, wave_id),
    ) as cur:
        return await cur.fetchall()


async def get_bilan_vague(
    db: aiosqlite.Connection, member_id: int, wave_id: int
) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM bilans_vague WHERE member_id = ? AND wave_id = ?",
        (member_id, wave_id),
    ) as cur:
        return await cur.fetchone()


async def upsert_bilan_vague(
    db: aiosqlite.Connection,
    member_id: int,
    wave_id: int,
    texte: str,
    ecrit_par: str,
    updated_at: str,
) -> None:
    await db.execute(
        "INSERT INTO bilans_vague (member_id, wave_id, texte, ecrit_par_discord_id, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (member_id, wave_id) DO UPDATE SET "
        "texte = excluded.texte, ecrit_par_discord_id = excluded.ecrit_par_discord_id, "
        "updated_at = excluded.updated_at",
        (member_id, wave_id, texte, ecrit_par, updated_at),
    )
    await db.commit()
