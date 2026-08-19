from datetime import date, datetime

import aiosqlite


async def list_distinct_creneaux(db: aiosqlite.Connection) -> list[str]:
    """Créneaux déjà utilisés dans l'historique — sert de suggestions autocomplete pour
    /session-start et /session-creer, en plus des créneaux standards (CRENEAUX)."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT DISTINCT creneau FROM sessions WHERE creneau IS NOT NULL"
    ) as cur:
        rows = await cur.fetchall()
    return [r["creneau"] for r in rows]


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


async def create_completed_session(
    db: aiosqlite.Connection,
    member_id: int,
    wave_id: int,
    semaine: int,
    session_date: date,
    creneau: str,
    canal_id: str | None,
    canal_nom: str | None,
    debut: datetime,
    fin: datetime | None,
    objectif: str | None,
    bilan: str | None,
    blocages: str | None,
) -> int:
    """Crée directement une session déjà clôturée — pour un rattrapage admin (ex.
    session tenue avant que le bot ne soit sur le serveur), contrairement à
    `start_session` qui laisse la session ouverte pour clôture ultérieure par le
    membre lui-même.

    `fin` par défaut = `debut` (jamais NULL) : `idx_one_open_session` n'autorise
    qu'une seule session à `fin IS NULL` par membre — la laisser NULL ici ferait
    passer ce rattrapage pour une session activement en cours côté `/session-start`.
    `statut` dérivé de la présence d'un bilan : `complète` si renseigné, sinon
    `incomplète` (même convention que l'historique importé)."""
    statut = "complète" if bilan else "incomplète"
    cur = await db.execute(
        """INSERT INTO sessions
           (member_id, wave_id, semaine, date, creneau, canal_id, canal_nom,
            debut, fin, objectif, bilan, blocages, statut)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            member_id,
            wave_id,
            semaine,
            session_date.isoformat(),
            creneau,
            canal_id,
            canal_nom,
            debut.isoformat(),
            (fin or debut).isoformat(),
            objectif or "",
            bilan,
            blocages,
            statut,
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


async def list_by_member_ids_and_semaine(
    db: aiosqlite.Connection, member_ids: list[int], semaine: int
) -> list[aiosqlite.Row]:
    """Recherche à travers toutes les vagues : sessions de ces membres pour ce numéro
    de semaine, quelle que soit la vague à laquelle elles appartiennent."""
    if not member_ids:
        return []
    db.row_factory = aiosqlite.Row
    placeholders = ",".join("?" for _ in member_ids)
    async with db.execute(
        f"""SELECT sessions.*, waves.nom AS wave_nom FROM sessions
            JOIN waves ON waves.id = sessions.wave_id
            WHERE sessions.member_id IN ({placeholders}) AND sessions.semaine = ?
            ORDER BY sessions.debut ASC""",
        (*member_ids, semaine),
    ) as cur:
        return await cur.fetchall()


async def list_filtered(
    db: aiosqlite.Connection,
    wave_id: int | None = None,
    semaine: int | None = None,
    member_id: int | None = None,
    statut: str | None = None,
    limit: int = 50,
) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    clauses = []
    params: list = []
    if wave_id is not None:
        clauses.append("sessions.wave_id = ?")
        params.append(wave_id)
    if semaine is not None:
        clauses.append("sessions.semaine = ?")
        params.append(semaine)
    if member_id is not None:
        clauses.append("sessions.member_id = ?")
        params.append(member_id)
    if statut is not None:
        clauses.append("sessions.statut = ?")
        params.append(statut)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    async with db.execute(
        f"""SELECT sessions.*, members.nom AS membre_nom, waves.nom AS wave_nom
            FROM sessions
            JOIN members ON members.id = sessions.member_id
            JOIN waves ON waves.id = sessions.wave_id
            {where}
            ORDER BY sessions.debut DESC
            LIMIT ?""",
        params,
    ) as cur:
        return await cur.fetchall()


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
