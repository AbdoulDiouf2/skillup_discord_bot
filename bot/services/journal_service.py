from datetime import datetime

from bot.config import TZ
from bot.db.binomes import get_partner_id
from bot.db.members import get_member, get_member_all_waves, get_member_by_id, update_objectif
from bot.db.sessions import delete_session, get_by_id as get_session_by_id
from bot.db.sessions import list_by_member_ids_and_semaine, list_by_member_wave, list_by_member_week
from bot.db.sessions import update_field as update_session_field
from bot.db.waves import get_active_wave, get_wave_by_id, list_waves
from bot.services.admin_service import SESSION_CHAMPS_EDITABLES
from bot.services.errors import ResolutionError
from bot.services.weeks import week_number_for_date


async def resolve_member_sessions(db, discord_id: str, vague_id: int | None, semaine: int | None):
    """Résout (sessions, nom_affiché, label, show_wave, member) selon la règle :
    - ni vague ni semaine -> vague active + semaine courante
    - semaine seul (sans vague) -> recherche à travers toutes les vagues (member=None,
      car la recherche porte sur plusieurs membership potentiellement liées à des
      threads objectif différents — pas de post unique à cibler)
    - vague précisée -> filtre strict sur cette vague (semaine optionnelle, défaut semaine courante de cette vague)
    """
    if vague_id is None and semaine is None:
        wave = await get_active_wave(db)
        if wave is None:
            raise ResolutionError("Aucune vague active.")
        member = await get_member(db, discord_id, wave["id"])
        if member is None:
            raise ResolutionError("Tu n'es pas enregistré comme membre de la vague active.")
        wave_start = datetime.fromisoformat(wave["date_debut"]).date()
        target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)
        sessions = await list_by_member_week(db, member["id"], wave["id"], target_semaine)
        return sessions, member["nom"], f"vague {wave['nom']}, semaine {target_semaine}", False, member

    if vague_id is None and semaine is not None:
        members = await get_member_all_waves(db, discord_id)
        if not members:
            raise ResolutionError("Tu n'es enregistré dans aucune vague.")
        member_ids = [m["id"] for m in members]
        sessions = await list_by_member_ids_and_semaine(db, member_ids, semaine)
        return sessions, members[0]["nom"], f"semaine {semaine} (toutes vagues)", True, None

    # vague_id précisé
    wave = await get_wave_by_id(db, vague_id)
    if wave is None:
        raise ResolutionError("Vague introuvable.")
    member = await get_member(db, discord_id, wave["id"])
    if member is None:
        raise ResolutionError(f"Tu n'es pas enregistré comme membre de la vague **{wave['nom']}**.")
    if semaine is not None:
        target_semaine = semaine
    else:
        wave_start = datetime.fromisoformat(wave["date_debut"]).date()
        target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)
    sessions = await list_by_member_week(db, member["id"], wave["id"], target_semaine)
    return sessions, member["nom"], f"vague {wave['nom']}, semaine {target_semaine}", False, member


async def resolve_member_sessions_vague(db, discord_id: str, vague_id: int):
    """Résout (sessions, nom_affiché, label, member) pour TOUTE la vague (toutes
    semaines confondues) — distinct de resolve_member_sessions, qui retombe sur la
    semaine courante quand `semaine` est omis. Sert au résumé "bilan de vague" (agrégat
    complet), pas au bilan hebdo."""
    wave = await get_wave_by_id(db, vague_id)
    if wave is None:
        raise ResolutionError("Vague introuvable.")
    member = await get_member(db, discord_id, wave["id"])
    if member is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    sessions = await list_by_member_wave(db, member["id"], wave["id"])
    return sessions, member["nom"], f"vague {wave['nom']} (toute la vague)", member


async def resolve_binome_journal(db, discord_id: str, vague_id: int | None, semaine: int | None):
    """Résout le journal du binôme d'un membre. Retourne
    (partner, sessions, wave, target_semaine). Mêmes règles que /binome-journal :
    - vague précisée -> cette vague
    - sinon, si semaine précisée et plusieurs vagues existent -> ambiguïté, erreur
    - sinon -> vague active
    """
    if vague_id is not None:
        wave = await get_wave_by_id(db, vague_id)
        if wave is None:
            raise ResolutionError("Vague introuvable.")
    else:
        if semaine is not None:
            all_waves = await list_waves(db)
            if len(all_waves) > 1:
                raise ResolutionError(
                    "Plusieurs vagues existent — précise le paramètre `vague` pour lever l'ambiguïté."
                )
        wave = await get_active_wave(db)
        if wave is None:
            raise ResolutionError("Aucune vague active.")

    member = await get_member(db, discord_id, wave["id"])
    if member is None:
        raise ResolutionError(f"Tu n'es pas enregistré comme membre de la vague **{wave['nom']}**.")

    if semaine is not None:
        target_semaine = semaine
    else:
        wave_start = datetime.fromisoformat(wave["date_debut"]).date()
        target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)

    partner_id = await get_partner_id(db, member["id"], wave["id"], target_semaine)
    if partner_id is None:
        raise ResolutionError(
            f"Tu étais en solo pour la semaine {target_semaine} (vague {wave['nom']}) — pas de binôme défini."
        )

    partner = await get_member_by_id(db, partner_id)
    sessions = await list_by_member_week(db, partner_id, wave["id"], target_semaine)
    return partner, sessions, wave, target_semaine


async def resolve_own_member(db, discord_id: str):
    """(wave, membre) de l'appelant sur la vague active. Erreur si pas membre — même
    message que /objectif-vague et /session-corriger côté bot."""
    wave = await get_active_wave(db)
    if wave is None:
        raise ResolutionError("Aucune vague active.")
    member = await get_member(db, discord_id, wave["id"])
    if member is None:
        raise ResolutionError("Tu n'es pas enregistré comme membre de la vague active.")
    return wave, member


async def resolve_objectif_vague_set(db, discord_id: str, valeur: str):
    """Définit l'objectif de vague de l'appelant. Ne gère PAS le fil forum `objectifs`
    (`_post_or_edit_objectif` côté bot, hors périmètre — nécessite un client discord.py
    vivant, absent du process API)."""
    wave, member = await resolve_own_member(db, discord_id)
    await update_objectif(db, member["id"], valeur)
    return wave, await get_member_by_id(db, member["id"])


async def _resolve_own_session(db, discord_id: str, session_id: int):
    """Mêmes règles que /session-corriger côté membre (bot/cogs/session.py:210-227) :
    ownership contre la vague ACTIVE (pas la vague de la session)."""
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise ResolutionError(f"Session `{session_id}` introuvable.")
    _wave, member = await resolve_own_member(db, discord_id)
    if session["member_id"] != member["id"]:
        raise ResolutionError("Tu ne peux corriger que tes propres sessions.")
    return session


async def resolve_session_corriger_self(db, discord_id: str, session_id: int, champ: str, valeur: str):
    if champ not in SESSION_CHAMPS_EDITABLES:
        raise ResolutionError(
            f"Champ invalide : `{champ}`. Valeurs possibles : {', '.join(SESSION_CHAMPS_EDITABLES)}."
        )
    await _resolve_own_session(db, discord_id, session_id)
    await update_session_field(db, session_id, champ, valeur)
    return await get_session_by_id(db, session_id)


async def resolve_session_supprimer_self(db, discord_id: str, session_id: int):
    session = await _resolve_own_session(db, discord_id, session_id)
    await delete_session(db, session_id)
    return session


def summarize_sessions(sessions: list) -> dict:
    """Agrège une liste de sessions en statistiques de bilan hebdomadaire."""
    nb_sessions = len(sessions)
    nb_completes = sum(1 for s in sessions if s["statut"] == "complète")
    nb_incompletes = sum(1 for s in sessions if s["statut"] == "incomplète")
    total_seconds = 0
    for s in sessions:
        if s["fin"]:
            debut = datetime.fromisoformat(s["debut"])
            fin = datetime.fromisoformat(s["fin"])
            total_seconds += (fin - debut).total_seconds()
    heures, reste = divmod(int(total_seconds), 3600)
    minutes = reste // 60
    duree_totale = f"{heures}h{minutes:02d}"
    blocages = [s["blocages"] for s in sessions if s["blocages"]]

    return {
        "nb_sessions": nb_sessions,
        "nb_completes": nb_completes,
        "nb_incompletes": nb_incompletes,
        "duree_totale": duree_totale,
        "blocages": blocages,
    }
