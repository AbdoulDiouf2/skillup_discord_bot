from fastapi import APIRouter, Depends, HTTPException

from api.deps import _check_admin, get_caller_discord_id, get_db, require_api_key, require_self_or_admin
from api.schemas import (
    AccessResponse,
    BilanResponse,
    BinomeJournalResponse,
    JournalResponse,
    SessionOut,
    VagueOut,
    VaguesResponse,
)
from bot.db.members import get_member, get_member_all_waves
from bot.db.waves import get_active_wave, get_wave_by_id
from bot.services.errors import ResolutionError
from bot.services.journal_service import (
    resolve_binome_journal,
    resolve_member_sessions,
    summarize_sessions,
)

router = APIRouter(prefix="/members/{discord_id}", tags=["journal"])


@router.get("/access", response_model=AccessResponse)
async def get_access(
    discord_id: str,
    db=Depends(get_db),
    _caller: str = Depends(get_caller_discord_id),
    _key: None = Depends(require_api_key),
):
    """Toujours 200 — statut de `discord_id` (jamais un 403/404, on veut juste savoir).
    is_participant : membre de la vague active. is_admin : rôle Admin SkillUp sur Discord."""
    wave = await get_active_wave(db)
    is_participant = False
    if wave is not None:
        member = await get_member(db, discord_id, wave["id"])
        is_participant = member is not None

    is_admin = await _check_admin(discord_id)

    return AccessResponse(is_participant=is_participant, is_admin=is_admin)


@router.get("/vagues", response_model=VaguesResponse)
async def get_vagues(
    discord_id: str,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Liste des vagues auxquelles ce membre a participé (une par wave_id distinct)."""
    member_rows = await get_member_all_waves(db, discord_id)
    wave_ids = {row["wave_id"] for row in member_rows}

    active_wave = await get_active_wave(db)
    active_id = active_wave["id"] if active_wave is not None else None

    vagues = []
    for wave_id in wave_ids:
        wave = await get_wave_by_id(db, wave_id)
        if wave is not None:
            vagues.append(VagueOut(id=wave["id"], nom=wave["nom"], active=wave["id"] == active_id))

    vagues.sort(key=lambda v: v.id, reverse=True)
    return VaguesResponse(vagues=vagues)


@router.get("/journal", response_model=JournalResponse)
async def get_journal(
    discord_id: str,
    vague: int | None = None,
    semaine: int | None = None,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    try:
        sessions, nom, label, show_wave, _member = await resolve_member_sessions(
            db, discord_id, vague, semaine
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return JournalResponse(
        nom=nom,
        label=label,
        show_wave=show_wave,
        sessions=[SessionOut(**dict(s)) for s in sessions],
    )


@router.get("/binome-journal", response_model=BinomeJournalResponse)
async def get_binome_journal(
    discord_id: str,
    vague: int | None = None,
    semaine: int | None = None,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    try:
        partner, sessions, wave, target_semaine = await resolve_binome_journal(
            db, discord_id, vague, semaine
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return BinomeJournalResponse(
        partenaire_nom=partner["nom"],
        label=f"vague {wave['nom']}, semaine {target_semaine}",
        sessions=[SessionOut(**dict(s)) for s in sessions],
    )


@router.get("/bilan", response_model=BilanResponse)
async def get_bilan(
    discord_id: str,
    vague: int | None = None,
    semaine: int | None = None,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    try:
        sessions, nom, label, _show_wave, _member = await resolve_member_sessions(
            db, discord_id, vague, semaine
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    resume = summarize_sessions(sessions)
    return BilanResponse(nom=nom, label=label, **resume)
