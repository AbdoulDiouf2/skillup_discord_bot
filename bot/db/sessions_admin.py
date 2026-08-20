import re
from datetime import datetime, timedelta

import aiosqlite

CRENEAU_FORMAT = re.compile(r"(\d{1,2})h-(\d{1,2})h")
DUREE_CRENEAU_DEFAUT = timedelta(hours=2)


def _duree_creneau(creneau: str | None) -> timedelta:
    """Durée nominale d'un créneau (ex. '21h-23h' -> 2h). Sert de référence pour juger
    si une session ouverte a dépassé son temps normal — un créneau non reconnu retombe
    sur la durée par défaut plutôt que de bloquer la clôture."""
    if not creneau:
        return DUREE_CRENEAU_DEFAUT
    match = CRENEAU_FORMAT.fullmatch(creneau)
    if not match:
        return DUREE_CRENEAU_DEFAUT
    debut_h, fin_h = int(match.group(1)), int(match.group(2))
    heures = fin_h - debut_h
    if heures <= 0:
        heures += 24
    return timedelta(hours=heures)


async def close_stale_open_sessions(db: aiosqlite.Connection, now: datetime) -> int:
    """RG-16 : clôture les sessions ouvertes dont la durée écoulée dépasse la durée
    nominale de leur créneau — pas une heure fixe (minuit), pour ne pas couper une
    session démarrée en retard mais toujours dans son temps normal (ex. connecté à 22h
    sur un créneau 21h-23h : sa session peut légitimement aller jusqu'à 00h)."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT id, creneau, debut FROM sessions WHERE fin IS NULL AND statut = 'ouverte'"
    ) as cur:
        candidats = await cur.fetchall()

    a_fermer = [
        row["id"]
        for row in candidats
        if now - datetime.fromisoformat(row["debut"]) >= _duree_creneau(row["creneau"])
    ]
    if not a_fermer:
        return 0

    placeholders = ", ".join("?" for _ in a_fermer)
    await db.execute(
        f"UPDATE sessions SET fin = ?, statut = 'incomplète' WHERE id IN ({placeholders})",
        (now.isoformat(), *a_fermer),
    )
    await db.commit()
    return len(a_fermer)
