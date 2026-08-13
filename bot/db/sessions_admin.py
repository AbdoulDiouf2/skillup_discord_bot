from datetime import datetime

import aiosqlite


async def close_stale_open_sessions(db: aiosqlite.Connection, minuit: datetime) -> int:
    """RG-16 : clôture à minuit les sessions restées ouvertes, statut incomplète."""
    cur = await db.execute(
        "UPDATE sessions SET fin = ?, statut = 'incomplète' WHERE fin IS NULL AND statut = 'ouverte'",
        (minuit.isoformat(),),
    )
    await db.commit()
    return cur.rowcount
