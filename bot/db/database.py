from pathlib import Path

import aiosqlite

from bot.config import DB_PATH

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema_sql)
        await db.commit()


def get_connection() -> aiosqlite.Connection:
    """Retourne une connexion aiosqlite prête à l'emploi (à utiliser avec `async with`)."""
    return aiosqlite.connect(DB_PATH)
