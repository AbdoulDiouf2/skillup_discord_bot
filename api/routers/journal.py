from fastapi import APIRouter, Depends, HTTPException

from api.deps import _check_admin, get_caller_discord_id, get_db, require_api_key, require_self_or_admin
from api.schemas import (
    AccessResponse,
    BilanResponse,
    BilanTexteOut,
    BinomeJournalResponse,
    JournalResponse,
    MemberOut,
    ObjectifVagueRequest,
    SessionCorrigerRequest,
    SessionOut,
    SessionSupprimerResponse,
    VagueOut,
    VaguesResponse,
)
from bot.db.members import get_member, get_member_all_waves
from bot.db.waves import get_active_wave, get_wave_by_id
from bot.services.errors import ResolutionError
from bot.services.admin_service import resolve_bilan_semaine_lire
from bot.services.journal_service import (
    resolve_binome_journal,
    resolve_member_sessions,
    resolve_member_sessions_vague,
    resolve_objectif_vague_set,
    resolve_own_member,
    resolve_session_corriger_self,
    resolve_session_supprimer_self,
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
        partenaire_discord_id=partner["discord_id"],
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


@router.get("/bilan-vague-info", response_model=BilanResponse)
async def get_bilan_vague_info(
    discord_id: str,
    vague: int,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Résumé informatif agrégé sur TOUTE la vague (toutes semaines confondues) —
    distinct de `/bilan?vague=X` qui, sans `semaine`, retombe sur la semaine courante
    seulement. Sert le panneau "résumé" du bilan de vague admin."""
    try:
        sessions, nom, label, _member = await resolve_member_sessions_vague(db, discord_id, vague)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    resume = summarize_sessions(sessions)
    return BilanResponse(nom=nom, label=label, **resume)


@router.get("/bilan-texte-semaine", response_model=BilanTexteOut | None)
async def get_bilan_texte_semaine(
    discord_id: str,
    semaine: int,
    vague: int | None = None,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Bilan hebdomadaire rédigé à la main par l'admin pour ce membre — lecture seule
    côté self-service (l'écriture reste réservée aux admins, cf. api/routers/admin.py).
    Distinct de `/bilan`, qui reste le résumé informatif calculé à la volée."""
    try:
        _wave, bilan = await resolve_bilan_semaine_lire(db, vague, discord_id, semaine)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    if bilan is None:
        return None
    return BilanTexteOut(
        texte=bilan["texte"],
        ecrit_par_discord_id=bilan["ecrit_par_discord_id"],
        updated_at=bilan["updated_at"],
    )


@router.get("/objectif-vague", response_model=MemberOut)
async def get_objectif_vague(
    discord_id: str,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    try:
        _wave, membre = await resolve_own_member(db, discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return MemberOut(**dict(membre))


@router.patch("/objectif-vague", response_model=MemberOut)
async def patch_objectif_vague(
    discord_id: str,
    body: ObjectifVagueRequest,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Définit/modifie l'objectif de vague de l'appelant. Équivalent API (champ DB
    uniquement) de `/objectif-vague` — ne gère pas le fil du forum Discord `objectifs`,
    qui reste géré par le bot (nécessite un client discord.py vivant)."""
    try:
        _wave, membre = await resolve_objectif_vague_set(db, discord_id, body.valeur)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return MemberOut(**dict(membre))


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def patch_own_session(
    discord_id: str,
    session_id: int,
    body: SessionCorrigerRequest,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Corrige une session appartenant à l'appelant. Équivalent API de
    `/session-corriger` côté membre (vérifie la propriété, contrairement à la version
    admin de `api/routers/admin.py`)."""
    try:
        session = await resolve_session_corriger_self(db, discord_id, session_id, body.champ, body.valeur)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return SessionOut(**dict(session))


@router.delete("/sessions/{session_id}", response_model=SessionSupprimerResponse)
async def delete_own_session(
    discord_id: str,
    session_id: int,
    db=Depends(get_db),
    _caller: str = Depends(require_self_or_admin()),
):
    """Supprime une session appartenant à l'appelant."""
    try:
        await resolve_session_supprimer_self(db, discord_id, session_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return SessionSupprimerResponse(id=session_id, message=f"Session {session_id} supprimée.")
