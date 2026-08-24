import re
from datetime import date, datetime

from bot.config import TZ
from bot.db.bilans import (
    get_bilan_semaine,
    get_bilan_vague,
    list_bilans_semaine_by_wave,
    upsert_bilan_semaine,
    upsert_bilan_vague,
)
from bot.db.binomes import BinomeError, define_binome, get_partner_id, list_binomes_semaine, remove_binome
from bot.db.coworking_channels import add_channel, list_channels, remove_channel
from bot.db.members import add_member, get_member, get_member_by_id, list_by_wave, set_thread_objectif_id
from bot.db.members import update_field as update_member_field
from bot.db.sessions import create_completed_session, delete_session, get_by_id, list_filtered, update_field
from bot.db.waves import (
    WaveError,
    activate_wave,
    close_wave,
    create_wave,
    get_active_wave,
    get_wave_by_id,
    list_waves,
)
from bot.services.errors import ResolutionError
from bot.services.weeks import week_number_for_date

# Mêmes champs éditables que la commande Discord /session-corriger (hors "suppression",
# qui est un domaine d'action séparé — cf. resolve_session_supprimer).
SESSION_CHAMPS_EDITABLES = ("objectif", "bilan", "blocages", "creneau")

# Mêmes valeurs que PROFILS côté bot (bot/cogs/admin.py) — dupliqué ici pour ne pas faire
# dépendre l'API du module cogs (qui importe discord.py, absent du process API).
MEMBRE_PROFILS = ("étudiant", "demandeur d'emploi", "cadre", "alternant", "autre")

# Mêmes champs éditables que la commande Discord /membre-editer.
MEMBRE_CHAMPS_EDITABLES = ("nom", "profil", "certif_ou_projet", "objectif_vague")


async def _resolve_wave(db, vague_id: int | None):
    if vague_id is not None:
        wave = await get_wave_by_id(db, vague_id)
        if wave is None:
            raise ResolutionError("Vague introuvable.")
        return wave
    wave = await get_active_wave(db)
    if wave is None:
        raise ResolutionError("Aucune vague active.")
    return wave


async def resolve_members_lister(db, vague_id: int | None):
    """Retourne (wave, membres). Mêmes règles que /membres-lister :
    vague donnée -> cette vague ; sinon -> vague active."""
    wave = await _resolve_wave(db, vague_id)
    membres = await list_by_wave(db, wave["id"])
    return wave, membres


async def resolve_sessions_lister(
    db,
    membre_discord_id: str | None,
    vague_id: int | None,
    semaine: int | None,
    statut: str | None,
    limit: int = 50,
) -> list:
    """Mêmes règles que /sessions-lister ET que resolve_members_lister : vague donnée
    -> cette vague ; sinon -> vague active (ResolutionError si aucune). Jamais de
    filtrage "toutes vagues" silencieux. Si `membre_discord_id` est fourni, résout
    aussi son member_id dans cette même vague, erreur s'il n'en est pas membre.

    `limit` par défaut à 50 pour rester identique au comportement historique de
    /sessions-lister côté Discord (tient dans un message). L'API web (qui n'a pas cette
    contrainte d'affichage) passe une valeur plus haute explicitement — cf. api/routers/admin.py."""
    wave = await _resolve_wave(db, vague_id)

    member_id = None
    if membre_discord_id is not None:
        m = await get_member(db, membre_discord_id, wave["id"])
        if m is None:
            raise ResolutionError(f"Le membre `{membre_discord_id}` n'est pas membre de cette vague.")
        member_id = m["id"]

    return await list_filtered(
        db, wave_id=wave["id"], semaine=semaine, member_id=member_id, statut=statut, limit=limit
    )


async def resolve_binomes_semaine(db, semaine: int | None, vague_id: int | None):
    """Retourne (wave, target_semaine, binomes). Mêmes règles que /binomes-semaine."""
    wave = await _resolve_wave(db, vague_id)
    if semaine is not None:
        target_semaine = semaine
    else:
        wave_start = datetime.fromisoformat(wave["date_debut"]).date()
        target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)
    binomes = await list_binomes_semaine(db, wave["id"], target_semaine)
    return wave, target_semaine, binomes


async def resolve_session_corriger(db, session_id: int, champ: str, valeur: str):
    """Corrige un champ d'une session existante. Mêmes règles que /session-corriger
    côté admin (pas de vérification de propriétaire — l'admin peut corriger n'importe
    quelle session)."""
    if champ not in SESSION_CHAMPS_EDITABLES:
        raise ResolutionError(
            f"Champ invalide : `{champ}`. Valeurs possibles : {', '.join(SESSION_CHAMPS_EDITABLES)}."
        )
    session = await get_by_id(db, session_id)
    if session is None:
        raise ResolutionError(f"Session `{session_id}` introuvable.")

    await update_field(db, session_id, champ, valeur)
    return await get_by_id(db, session_id)


async def resolve_session_creer(
    db,
    vague_id: int | None,
    discord_id: str,
    date_session: str,
    creneau: str,
    heure_debut: str,
    heure_fin: str | None,
    objectif: str | None,
    bilan: str | None,
    canal_id: str | None,
    canal_nom: str | None,
    blocages: str | None,
):
    """Crée une session déjà clôturée pour un membre — rattrapage admin (ex. séance
    tenue avant que le bot ne soit sur le serveur). Seuls membre/date/créneau/heure
    de début sont obligatoires : heure de fin, objectif et bilan peuvent manquer sur
    un rattrapage approximatif (statut alors `incomplète`, cf. `create_completed_session`).
    Mêmes règles que la commande Discord `/session-creer`. Retourne la session créée."""
    # Format libre (pas restreint à CRENEAUX) : le rattrapage doit pouvoir couvrir des
    # créneaux hors de la liste standard (ex. "17h-19h", déjà présents dans l'historique
    # importé). On valide juste la forme "HHh-HHh" pour éviter une saisie incohérente.
    if not re.fullmatch(r"\d{1,2}h-\d{1,2}h", creneau):
        raise ResolutionError(f"Créneau invalide : `{creneau}`. Format attendu : `HHh-HHh` (ex. 19h-21h).")

    try:
        y, m, d = map(int, date_session.split("-"))
        session_date = date(y, m, d)
    except ValueError as e:
        raise ResolutionError("Date invalide — format attendu AAAA-MM-JJ.") from e

    try:
        hh, mm = map(int, heure_debut.split(":"))
        debut = datetime(y, m, d, hh, mm, tzinfo=TZ)
        fin = None
        if heure_fin:
            fh, fm = map(int, heure_fin.split(":"))
            fin = datetime(y, m, d, fh, fm, tzinfo=TZ)
    except ValueError as e:
        raise ResolutionError("Heure invalide — format attendu HH:MM.") from e

    if fin is not None and fin <= debut:
        raise ResolutionError("L'heure de fin doit être après l'heure de début.")

    wave = await _resolve_wave(db, vague_id)

    member = await get_member(db, discord_id, wave["id"])
    if member is None:
        raise ResolutionError(f"Ce membre n'est pas dans la vague **{wave['nom']}**.")

    semaine = week_number_for_date(session_date, datetime.fromisoformat(wave["date_debut"]).date())

    session_id = await create_completed_session(
        db,
        member_id=member["id"],
        wave_id=wave["id"],
        semaine=semaine,
        session_date=session_date,
        creneau=creneau,
        canal_id=canal_id,
        canal_nom=canal_nom,
        debut=debut,
        fin=fin,
        objectif=objectif,
        bilan=bilan,
        blocages=blocages,
    )
    return await get_by_id(db, session_id)


async def resolve_membre_ajouter(
    db, vague_id: int | None, discord_id: str, nom: str, profil: str, certif_ou_projet: str | None
):
    """Ajoute un membre à une vague. Mêmes règles que /membre-ajouter : refuse si déjà
    membre de cette vague, valide le profil contre la liste fermée. Retourne (wave, membre)."""
    if profil not in MEMBRE_PROFILS:
        raise ResolutionError(
            f"Profil invalide : `{profil}`. Valeurs possibles : {', '.join(MEMBRE_PROFILS)}."
        )
    wave = await _resolve_wave(db, vague_id)

    existing = await get_member(db, discord_id, wave["id"])
    if existing is not None:
        raise ResolutionError(f"Ce membre est déjà dans la vague **{wave['nom']}**.")

    member_id = await add_member(db, discord_id, nom, profil, wave["id"], certif_ou_projet)
    return wave, await get_member_by_id(db, member_id)


async def resolve_membre_editer(db, vague_id: int | None, discord_id: str, champ: str, valeur: str):
    """Édite un champ d'un membre existant. Mêmes règles que /membre-editer. Retourne
    (wave, membre)."""
    if champ not in MEMBRE_CHAMPS_EDITABLES:
        raise ResolutionError(
            f"Champ invalide : `{champ}`. Valeurs possibles : {', '.join(MEMBRE_CHAMPS_EDITABLES)}."
        )
    wave = await _resolve_wave(db, vague_id)

    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")

    await update_member_field(db, membre["id"], champ, valeur)
    return wave, await get_member_by_id(db, membre["id"])


async def resolve_membre_objectif_sync_prepare(db, vague_id: int | None, discord_id: str):
    """Résout le membre et vérifie qu'un post objectif est bien rattaché, avant que le
    routeur aille chercher son contenu réel sur Discord — reste indépendant de
    discord.py/httpx comme le reste de ce module, l'appel HTTP se fait côté routeur.
    Retourne (wave, membre)."""
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    if not membre["thread_objectif_id"]:
        raise ResolutionError(
            "Aucun post objectif rattaché à ce membre — utilise d'abord /membre-lier-thread."
        )
    return wave, membre


async def resolve_membres_objectif_sync_prepare(db, vague_id: int | None):
    """Retourne (wave, membres) — uniquement les membres de la vague ayant un post
    objectif rattaché (thread_objectif_id non nul), cible de la synchro en masse."""
    wave = await _resolve_wave(db, vague_id)
    membres = await list_by_wave(db, wave["id"])
    cibles = [m for m in membres if m["thread_objectif_id"]]
    return wave, cibles


async def resolve_membre_objectif_sync_apply(db, member_id: int, contenu: str):
    """Écrit le contenu récupéré sur Discord dans `objectif_vague` — séparé de
    resolve_membre_objectif_sync_prepare pour garder l'appel HTTP Discord côté routeur
    (ce module reste indépendant de httpx/discord.py, même convention que send_dm)."""
    await update_member_field(db, member_id, "objectif_vague", contenu)
    return await get_member_by_id(db, member_id)


async def resolve_binome_definir(
    db, vague_id: int | None, semaine: int, discord_id_a: str, discord_id_b: str
):
    """Définit un binôme pour (vague, semaine). Mêmes règles que /binome-definir :
    les deux membres doivent être enregistrés dans la vague résolue (vague donnée,
    sinon vague active). Retourne (wave, membre_a, membre_b)."""
    wave = await _resolve_wave(db, vague_id)

    membre_a = await get_member(db, discord_id_a, wave["id"])
    membre_b = await get_member(db, discord_id_b, wave["id"])
    if membre_a is None or membre_b is None:
        raise ResolutionError(
            f"Les deux membres doivent être enregistrés dans la vague **{wave['nom']}**."
        )

    try:
        await define_binome(db, wave["id"], semaine, membre_a["id"], membre_b["id"])
    except BinomeError as e:
        raise ResolutionError(str(e)) from e

    return wave, membre_a, membre_b


async def resolve_binome_retirer(db, vague_id: int | None, semaine: int, discord_id: str):
    """Dissout le binôme d'un membre pour (vague, semaine). Mêmes règles que
    /binome-retirer. Retourne (wave, membre, partenaire_ou_None) — le partenaire est
    résolu *avant* suppression pour pouvoir le prévenir par DM."""
    wave = await _resolve_wave(db, vague_id)

    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")

    partner_id = await get_partner_id(db, membre["id"], wave["id"], semaine)
    partenaire = await get_member_by_id(db, partner_id) if partner_id else None

    removed = await remove_binome(db, wave["id"], semaine, membre["id"])
    if not removed:
        raise ResolutionError(f"Ce membre n'était dans aucun binôme pour la semaine {semaine}.")

    return wave, membre, partenaire


async def resolve_vague_creer(db, nom: str, date_debut: date, date_fin: date):
    """Crée une vague en brouillon. Mêmes règles que /vague-creer (jamais activée
    automatiquement — cf. RG-14)."""
    wave_id = await create_wave(db, nom, date_debut, date_fin)
    return await get_wave_by_id(db, wave_id)


async def resolve_vague_activer(db, vague_id: int):
    """Active une vague en brouillon. Mêmes règles que /vague-activer (refuse si une
    autre vague est déjà active, ou si la vague n'est pas en brouillon)."""
    try:
        return await activate_wave(db, vague_id)
    except WaveError as e:
        raise ResolutionError(str(e)) from e


async def resolve_vague_cloturer(db, vague_id: int | None):
    """Clôture une vague (par défaut la vague active). Mêmes règles que /vague-cloturer."""
    try:
        return await close_wave(db, vague_id)
    except WaveError as e:
        raise ResolutionError(str(e)) from e


async def resolve_vagues_lister(db, statut: str | None):
    """Liste toutes les vagues, filtrables par statut. Mêmes règles que /vague-lister."""
    return await list_waves(db, statut)


async def resolve_salon_ajouter(db, vague_id: int | None, canal_id: str, canal_nom: str):
    """Ajoute (ou réactive) un salon de coworking pour une vague. Mêmes règles que
    /salon-coworking-ajouter (idempotent : `add_channel` fait un upsert)."""
    wave = await _resolve_wave(db, vague_id)
    await add_channel(db, canal_id, canal_nom, wave["id"])
    return wave


async def resolve_salon_retirer(db, vague_id: int | None, canal_id: str):
    """Désactive un salon de coworking pour une vague. Mêmes règles que
    /salon-coworking-retirer (soft-delete : `actif = FALSE`, pas une suppression)."""
    wave = await _resolve_wave(db, vague_id)
    await remove_channel(db, canal_id, wave["id"])
    return wave


async def resolve_salons_lister(db, vague_id: int | None, actif_seulement: bool):
    """Liste les salons de coworking. Mêmes règles que /salons-coworking-lister —
    contrairement aux autres domaines, `vague_id=None` liste TOUTES les vagues (pas
    seulement la vague active), pour rester cohérent avec le comportement Discord."""
    return await list_channels(db, vague_id, actif_seulement)


async def resolve_bilan_semaine_lire(db, vague_id: int | None, discord_id: str, semaine: int):
    """Retourne (wave, texte du bilan hebdo ou None). Mêmes règles de résolution de
    membre que /membre-editer (membre doit être enregistré dans la vague résolue)."""
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    bilan = await get_bilan_semaine(db, membre["id"], wave["id"], semaine)
    return wave, bilan


async def resolve_bilan_semaine_ecrire(
    db, vague_id: int | None, discord_id: str, semaine: int, texte: str, ecrit_par: str
):
    """Écrit (upsert) le bilan hebdo d'un membre pour une semaine donnée. Rédigé à la
    main par l'admin — jamais généré/pré-rempli automatiquement (cf. `/bilan` pour le
    résumé informatif qui aide à la rédaction, non stocké)."""
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    updated_at = datetime.now(TZ).isoformat()
    await upsert_bilan_semaine(db, membre["id"], wave["id"], semaine, texte, ecrit_par, updated_at)
    return wave, await get_bilan_semaine(db, membre["id"], wave["id"], semaine), membre


async def resolve_bilans_semaine_lister(db, vague_id: int | None, semaine: int):
    """Liste, pour chaque membre de la vague résolue, son bilan hebdo pour `semaine`
    (texte/ecrit_par/updated_at à None si pas encore rédigé). Retourne (wave, rows)."""
    wave = await _resolve_wave(db, vague_id)
    rows = await list_bilans_semaine_by_wave(db, wave["id"], semaine)
    return wave, rows


async def resolve_bilan_vague_lire(db, vague_id: int | None, discord_id: str):
    """Retourne (wave, texte du bilan de vague ou None)."""
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    bilan = await get_bilan_vague(db, membre["id"], wave["id"])
    return wave, bilan


async def resolve_bilan_vague_ecrire(db, vague_id: int | None, discord_id: str, texte: str, ecrit_par: str):
    """Écrit (upsert) le bilan de synthèse de vague d'un membre. Rédigé à la main par
    l'admin, même logique que resolve_bilan_semaine_ecrire."""
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    updated_at = datetime.now(TZ).isoformat()
    await upsert_bilan_vague(db, membre["id"], wave["id"], texte, ecrit_par, updated_at)
    return wave, await get_bilan_vague(db, membre["id"], wave["id"])


def parse_thread_id(raw: str) -> int | None:
    """Accepte un ID brut ou un lien https://discord.com/channels/<guild>/<channel>[/<message>].
    Copie de bot/cogs/admin.py::_parse_thread_id — fonction pure, dupliquée ici plutôt
    qu'importée du cog pour ne pas faire dépendre le service layer de discord.py."""
    digits = re.findall(r"\d{15,25}", raw)
    if not digits:
        return None
    return int(digits[1]) if len(digits) >= 2 else int(digits[0])


async def resolve_membre_lier_thread(db, vague_id: int | None, discord_id: str, lien_ou_id: str):
    """Rattache manuellement un thread objectif existant. Mêmes règles que /membre-lier-thread."""
    thread_id = parse_thread_id(lien_ou_id)
    if thread_id is None:
        raise ResolutionError("Lien ou ID de post invalide.")
    wave = await _resolve_wave(db, vague_id)
    membre = await get_member(db, discord_id, wave["id"])
    if membre is None:
        raise ResolutionError(f"Ce membre n'est pas enregistré dans la vague **{wave['nom']}**.")
    await set_thread_objectif_id(db, membre["id"], str(thread_id))
    return wave, await get_member_by_id(db, membre["id"])


async def resolve_session_supprimer(db, session_id: int):
    """Supprime une session. Retourne la session telle qu'elle était avant suppression
    (pour que l'appelant puisse en afficher un récapitulatif)."""
    session = await get_by_id(db, session_id)
    if session is None:
        raise ResolutionError(f"Session `{session_id}` introuvable.")

    await delete_session(db, session_id)
    return session
