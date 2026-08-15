from datetime import date, datetime

import pytest

from bot.db.binomes import define_binome
from bot.db.members import add_member
from bot.db.sessions import start_session
from bot.db.waves import close_wave, create_wave, get_active_wave
from bot.services.admin_service import (
    resolve_binomes_semaine,
    resolve_members_lister,
    resolve_sessions_lister,
)
from bot.services.errors import ResolutionError

pytestmark = pytest.mark.asyncio


async def test_resolve_members_lister(db):
    wave_id = await create_wave(db, "Test Admin", date(2026, 8, 2), date(2026, 8, 30))
    await add_member(db, "discordA", "Alice", "étudiant", wave_id)
    await add_member(db, "discordB", "Bob", "cadre", wave_id)

    wave, membres = await resolve_members_lister(db, wave_id)
    assert wave["id"] == wave_id
    assert len(membres) == 2


async def test_resolve_members_lister_unknown_wave_raises(db):
    with pytest.raises(ResolutionError):
        await resolve_members_lister(db, 999999999)


async def test_resolve_sessions_lister_filters_by_member(db):
    wave_id = await create_wave(db, "Test Admin2", date(2026, 8, 2), date(2026, 8, 30))
    m1 = await add_member(db, "discordC", "Carl", "autre", wave_id)
    m2 = await add_member(db, "discordD", "Dana", "autre", wave_id)
    await start_session(
        db, m1, wave_id, 1, date(2026, 8, 3), "5h-7h", None, None,
        datetime(2026, 8, 3, 5, 0), "Obj Carl",
    )
    await start_session(
        db, m2, wave_id, 1, date(2026, 8, 3), "19h-21h", None, None,
        datetime(2026, 8, 3, 19, 0), "Obj Dana",
    )

    all_sessions = await resolve_sessions_lister(db, None, wave_id, None, None)
    assert len(all_sessions) == 2

    carl_sessions = await resolve_sessions_lister(db, "discordC", wave_id, None, None)
    assert len(carl_sessions) == 1


async def test_resolve_sessions_lister_unknown_member_raises(db):
    wave_id = await create_wave(db, "Test Admin3", date(2026, 8, 2), date(2026, 8, 30))
    with pytest.raises(ResolutionError):
        await resolve_sessions_lister(db, "unknown", wave_id, None, None)


async def test_resolve_sessions_lister_defaults_to_active_wave_not_all_waves(db):
    """Régression : sans vague_id, ne doit jamais renvoyer "toutes vagues" — doit se
    limiter à la vague active, comme resolve_members_lister."""
    active = await get_active_wave(db)
    assert active is not None, "précondition du test : une vague active doit exister"

    other_wave_id = await create_wave(db, "Wave inactive", date(2026, 9, 2), date(2026, 9, 30))
    m = await add_member(db, "discordG", "Gus", "autre", other_wave_id)
    await start_session(
        db, m, other_wave_id, 1, date(2026, 9, 3), "5h-7h", None, None,
        datetime(2026, 9, 3, 5, 0), "Obj Gus (vague inactive)",
    )

    sessions = await resolve_sessions_lister(db, None, None, None, None)
    assert all(s["wave_id"] == active["id"] for s in sessions)
    assert not any(s["wave_id"] == other_wave_id for s in sessions)


async def test_resolve_sessions_lister_no_active_wave_raises(db):
    active = await get_active_wave(db)
    assert active is not None, "précondition du test : une vague active doit exister"
    await close_wave(db, active["id"])

    with pytest.raises(ResolutionError, match="Aucune vague active"):
        await resolve_sessions_lister(db, None, None, None, None)


async def test_resolve_binomes_semaine(db):
    wave_id = await create_wave(db, "Test Admin4", date(2026, 8, 2), date(2026, 8, 30))
    m1 = await add_member(db, "discordE", "Eve", "autre", wave_id)
    m2 = await add_member(db, "discordF", "Faye", "autre", wave_id)
    await define_binome(db, wave_id, 2, m1, m2)

    wave, target_semaine, binomes = await resolve_binomes_semaine(db, 2, wave_id)
    assert target_semaine == 2
    assert len(binomes) == 1
    assert {binomes[0]["nom_a"], binomes[0]["nom_b"]} == {"Eve", "Faye"}
