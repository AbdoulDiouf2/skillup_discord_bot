import os

os.environ.setdefault("ENV", "dev")

import pytest_asyncio

from bot.db.database import Connection, _get_pool, close_pool, init_db


@pytest_asyncio.fixture
async def db():
    """Connexion transactionnelle, sur un pool créé et refermé pour ce test
    (évite tout souci de event loop partagée entre fixtures et tests). Tout ce
    qu'un test écrit est annulé (rollback) — jamais de pollution des vraies
    données de la base de dev."""
    await init_db()
    pool = await _get_pool()
    raw = await pool.acquire()
    tx = raw.transaction()
    await tx.start()
    try:
        yield Connection(raw)
    finally:
        await tx.rollback()
        await pool.release(raw)
        await close_pool()
