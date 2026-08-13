from datetime import date, datetime

import aiosqlite
import pytest

from bot.db.members import add_member
from bot.db.sessions import get_open_session, start_session
from bot.db.waves import create_wave

pytestmark = pytest.mark.asyncio


async def _setup_db():
    db = await aiosqlite.connect(":memory:")
    with open("bot/db/schema.sql", encoding="utf-8") as f:
        await db.executescript(f.read())
    return db


async def _seed_member(db):
    wave_id = await create_wave(db, "Test", date(2026, 8, 2), date(2026, 8, 30))
    member_id = await add_member(db, "discord123", "Testeur", "étudiant", wave_id)
    return wave_id, member_id


async def test_rg02_second_open_session_rejected_by_db():
    db = await _setup_db()
    try:
        wave_id, member_id = await _seed_member(db)
        await start_session(
            db, member_id, wave_id, 1, date(2026, 8, 3), "5h-7h", None, None,
            datetime(2026, 8, 3, 5, 0), "Objectif 1",
        )
        assert await get_open_session(db, member_id) is not None

        with pytest.raises(aiosqlite.IntegrityError):
            await start_session(
                db, member_id, wave_id, 1, date(2026, 8, 3), "19h-21h", None, None,
                datetime(2026, 8, 3, 19, 0), "Objectif 2",
            )
    finally:
        await db.close()


async def test_rg13_multi_session_same_day_after_closing_first():
    db = await _setup_db()
    try:
        wave_id, member_id = await _seed_member(db)
        sid1 = await start_session(
            db, member_id, wave_id, 1, date(2026, 8, 3), "5h-7h", None, None,
            datetime(2026, 8, 3, 5, 0), "Objectif 1",
        )
        await db.execute(
            "UPDATE sessions SET fin = ?, statut = 'complète' WHERE id = ?",
            (datetime(2026, 8, 3, 7, 0).isoformat(), sid1),
        )
        await db.commit()

        sid2 = await start_session(
            db, member_id, wave_id, 1, date(2026, 8, 3), "19h-21h", None, None,
            datetime(2026, 8, 3, 19, 0), "Objectif 2",
        )
        assert sid2 != sid1
        open_session = await get_open_session(db, member_id)
        assert open_session["id"] == sid2
    finally:
        await db.close()
