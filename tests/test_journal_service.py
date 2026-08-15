from datetime import date, datetime

import pytest

from bot.db.binomes import define_binome
from bot.db.members import add_member
from bot.db.sessions import end_session, start_session
from bot.db.waves import create_wave
from bot.services.errors import ResolutionError
from bot.services.journal_service import (
    resolve_binome_journal,
    resolve_member_sessions,
    summarize_sessions,
)

pytestmark = pytest.mark.asyncio


async def _seed(db):
    wave_id = await create_wave(db, "Test Journal", date(2026, 8, 2), date(2026, 8, 30))
    member_id = await add_member(db, "discordX", "Testeur", "étudiant", wave_id)
    return wave_id, member_id


async def test_resolve_member_sessions_with_vague(db):
    wave_id, member_id = await _seed(db)
    sid = await start_session(
        db, member_id, wave_id, 1, date(2026, 8, 3), "5h-7h", None, None,
        datetime(2026, 8, 3, 5, 0), "Objectif test",
    )
    await end_session(db, sid, datetime(2026, 8, 3, 7, 0), "Bilan test", None)

    sessions, nom, label, show_wave, member = await resolve_member_sessions(db, "discordX", wave_id, 1)
    assert len(sessions) == 1
    assert nom == "Testeur"
    assert show_wave is False
    assert member["id"] == member_id

    resume = summarize_sessions(sessions)
    assert resume["nb_sessions"] == 1
    assert resume["nb_completes"] == 1
    assert resume["duree_totale"] == "2h00"


async def test_resolve_member_sessions_unknown_member_raises(db):
    wave_id, _ = await _seed(db)
    with pytest.raises(ResolutionError):
        await resolve_member_sessions(db, "unknown-discord-id", wave_id, 1)


async def test_resolve_member_sessions_unknown_wave_raises(db):
    with pytest.raises(ResolutionError):
        await resolve_member_sessions(db, "discordX", 999999999, 1)


async def test_resolve_binome_journal_ambiguous_without_vague(db):
    # Deux vagues créées dans cette transaction : garantit l'ambiguïté quel que
    # soit l'état réel de la base de dev (qui peut déjà en avoir d'autres).
    await create_wave(db, "W1", date(2026, 8, 2), date(2026, 8, 30))
    await create_wave(db, "W2", date(2026, 9, 2), date(2026, 9, 30))
    with pytest.raises(ResolutionError, match="Plusieurs vagues"):
        await resolve_binome_journal(db, "discordX", None, 1)


async def test_resolve_binome_journal_solo_raises(db):
    wave_id, _ = await _seed(db)
    with pytest.raises(ResolutionError, match="solo"):
        await resolve_binome_journal(db, "discordX", wave_id, 1)


async def test_resolve_binome_journal_with_partner(db):
    wave_id, member_id = await _seed(db)
    partner_id = await add_member(db, "discordY", "Partenaire", "cadre", wave_id)
    await define_binome(db, wave_id, 1, member_id, partner_id)
    sid = await start_session(
        db, partner_id, wave_id, 1, date(2026, 8, 3), "5h-7h", None, None,
        datetime(2026, 8, 3, 5, 0), "Obj partenaire",
    )
    await end_session(db, sid, datetime(2026, 8, 3, 7, 0), "Bilan partenaire", None)

    partner, sessions, wave, target_semaine = await resolve_binome_journal(db, "discordX", wave_id, 1)
    assert partner["nom"] == "Partenaire"
    assert len(sessions) == 1
    assert target_semaine == 1
