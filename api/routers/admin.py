from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api import ai_provider, discord_client
from api.config import ANTHROPIC_API_KEY, GROQ_API_KEY
from api.deps import get_db, get_caller_discord_id, require_admin
from api.schemas import (
    AiModelsResponse,
    AiSettingsOut,
    AiSettingsRequest,
    BilanMembreOut,
    BilansSemaineListResponse,
    BilanSuggestionResponse,
    BilansVagueListResponse,
    BilanTexteOut,
    BilanTexteRequest,
    BinomeActionResponse,
    BinomeDefinirRequest,
    BinomeOut,
    BinomesResponse,
    DiscordMemberOut,
    DiscordMembersResponse,
    DiscordVoiceChannelOut,
    DiscordVoiceChannelsResponse,
    MemberOut,
    MembersResponse,
    MembreAjouterRequest,
    MembreAjouterResponse,
    MembreEditerRequest,
    MembreLierThreadRequest,
    ObjectifsSyncResponse,
    ObjectifSyncResultOut,
    SalonAjouterRequest,
    SalonOut,
    SalonsListResponse,
    SessionCorrigerRequest,
    SessionCreerRequest,
    SessionOut,
    SessionsListResponse,
    SessionSupprimerResponse,
    VagueAdminOut,
    VagueCreerRequest,
)
from bot.services.admin_service import (
    resolve_ai_settings_ecrire,
    resolve_ai_settings_lire,
    resolve_bilan_semaine_ecrire,
    resolve_bilan_semaine_lire,
    resolve_bilans_semaine_lister,
    resolve_bilans_vague_lister,
    resolve_bilan_vague_ecrire,
    resolve_bilan_vague_lire,
    resolve_binome_definir,
    resolve_binome_retirer,
    resolve_binomes_semaine,
    resolve_membre_ajouter,
    resolve_membre_editer,
    resolve_membre_lier_thread,
    resolve_wave_et_membre,
    resolve_membre_objectif_sync_apply,
    resolve_membre_objectif_sync_prepare,
    resolve_membres_objectif_sync_prepare,
    resolve_members_lister,
    resolve_salon_ajouter,
    resolve_salon_retirer,
    resolve_salons_lister,
    resolve_session_corriger,
    resolve_session_creer,
    resolve_session_supprimer,
    resolve_sessions_lister,
    resolve_vague_activer,
    resolve_vague_cloturer,
    resolve_vague_creer,
)
from bot.services.bilan_ai_service import build_bilan_semaine_prompt, build_bilan_vague_prompt
from bot.services.errors import ResolutionError

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/discord/members", response_model=DiscordMembersResponse)
async def get_discord_members():
    """Liste brute de tous les membres du serveur Discord (pas seulement ceux inscrits
    à une vague) — le croisement avec les membres SkillUp se fait côté frontend."""
    try:
        members = await discord_client.get_guild_members()
    except discord_client.DiscordAPIError as e:
        raise HTTPException(503, str(e)) from e

    return DiscordMembersResponse(members=[DiscordMemberOut(**m) for m in members])


@router.get("/discord/voice-channels", response_model=DiscordVoiceChannelsResponse)
async def get_discord_voice_channels():
    """Liste les salons vocaux standards (type 2) du serveur Discord — sert à peupler
    le sélecteur "Ajouter un salon" côté frontend, plutôt qu'une saisie manuelle."""
    try:
        channels = await discord_client.get_voice_channels()
    except discord_client.DiscordAPIError as e:
        raise HTTPException(503, str(e)) from e

    return DiscordVoiceChannelsResponse(channels=[DiscordVoiceChannelOut(**c) for c in channels])


@router.post("/vagues", response_model=VagueAdminOut)
async def post_vague(body: VagueCreerRequest, db=Depends(get_db)):
    """Crée une vague en brouillon. Équivalent API de /vague-creer — jamais activée
    automatiquement (cf. RG-14, `/vague-activer` séparé)."""
    try:
        debut = date.fromisoformat(body.date_debut)
        fin = date.fromisoformat(body.date_fin)
    except ValueError as e:
        raise HTTPException(400, "Format de date invalide (attendu AAAA-MM-JJ).") from e

    wave = await resolve_vague_creer(db, body.nom, debut, fin)
    return VagueAdminOut(**dict(wave))


@router.patch("/vagues/{vague_id}/activer", response_model=VagueAdminOut)
async def patch_vague_activer(vague_id: int, db=Depends(get_db)):
    """Active une vague en brouillon. Équivalent API de /vague-activer."""
    try:
        wave = await resolve_vague_activer(db, vague_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return VagueAdminOut(**dict(wave))


@router.patch("/vagues/cloturer", response_model=VagueAdminOut)
async def patch_vague_cloturer(vague_id: int | None = None, db=Depends(get_db)):
    """Clôture une vague (par défaut la vague active). Équivalent API de /vague-cloturer."""
    try:
        wave = await resolve_vague_cloturer(db, vague_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return VagueAdminOut(**dict(wave))


@router.get("/salons", response_model=SalonsListResponse)
async def get_salons(vague: int | None = None, actif: bool = False, db=Depends(get_db)):
    """Liste les salons de coworking. Équivalent API de /salons-coworking-lister —
    sans `vague`, liste TOUTES les vagues (comportement Discord d'origine)."""
    salons = await resolve_salons_lister(db, vague, actif)
    return SalonsListResponse(salons=[SalonOut(**dict(s)) for s in salons])


@router.post("/salons", response_model=SalonOut)
async def post_salon(body: SalonAjouterRequest, db=Depends(get_db)):
    """Ajoute (ou réactive) un salon de coworking pour une vague. Équivalent API de
    /salon-coworking-ajouter."""
    wave = await resolve_salon_ajouter(db, body.vague, body.canal_id, body.canal_nom)
    return SalonOut(canal_id=body.canal_id, canal_nom=body.canal_nom, actif=True, wave_nom=wave["nom"])


@router.delete("/salons")
async def delete_salon(canal_id: str, vague: int | None = None, db=Depends(get_db)):
    """Désactive un salon de coworking (soft-delete). Équivalent API de
    /salon-coworking-retirer."""
    wave = await resolve_salon_retirer(db, vague, canal_id)
    return {"canal_id": canal_id, "wave_nom": wave["nom"], "message": "Salon retiré."}


@router.get("/members", response_model=MembersResponse)
async def get_members(vague: int | None = None, db=Depends(get_db)):
    try:
        wave, membres = await resolve_members_lister(db, vague)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return MembersResponse(
        wave_id=wave["id"],
        wave_nom=wave["nom"],
        membres=[MemberOut(**dict(m)) for m in membres],
    )


@router.post("/members", response_model=MembreAjouterResponse)
async def post_member(body: MembreAjouterRequest, db=Depends(get_db)):
    """Ajoute un membre à une vague. Équivalent API de /membre-ajouter — envoie un DM
    de bienvenue (best-effort, jamais fatal)."""
    try:
        wave, membre = await resolve_membre_ajouter(
            db, body.vague, body.discord_id, body.nom, body.profil, body.certif_ou_projet
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    dm_ok = await discord_client.send_dm(
        body.discord_id,
        f"Tu as été ajouté à la vague **{wave['nom']}** ({body.profil}). Bienvenue !\n\n"
        f"Pense à poster ton objectif de vague dans le forum `objectifs`, ou renseigne-le via "
        f"`/objectif-vague` (dans un salon du serveur). Pour démarrer ta première session : "
        f"`/session-start`, également sur le serveur.",
    )

    return MembreAjouterResponse(
        id=membre["id"],
        discord_id=membre["discord_id"],
        nom=membre["nom"],
        profil=membre["profil"],
        certif_ou_projet=membre["certif_ou_projet"],
        dm_ok=dm_ok,
    )


@router.patch("/members/{discord_id}", response_model=MemberOut)
async def patch_member(discord_id: str, body: MembreEditerRequest, db=Depends(get_db)):
    """Édite un champ d'un membre existant. Équivalent API de /membre-editer."""
    try:
        _wave, membre = await resolve_membre_editer(db, body.vague, discord_id, body.champ, body.valeur)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return MemberOut(**dict(membre))


@router.patch("/members/{discord_id}/thread-objectif", response_model=MemberOut)
async def patch_membre_lier_thread(discord_id: str, body: MembreLierThreadRequest, db=Depends(get_db)):
    """Rattache manuellement le post objectif existant d'un membre. Équivalent API de
    /membre-lier-thread (rattrapage manuel ponctuel — cas des membres dont le post a
    été créé à la main avant l'automatisation `/objectif-vague`)."""
    try:
        _wave, membre = await resolve_membre_lier_thread(db, body.vague, discord_id, body.lien_ou_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return MemberOut(**dict(membre))


@router.post("/members/{discord_id}/objectif-vague/sync", response_model=MemberOut)
async def post_membre_objectif_sync(discord_id: str, vague: int | None = None, db=Depends(get_db)):
    """Récupère le contenu réel du post objectif Discord déjà rattaché (thread_objectif_id)
    et l'écrit dans `objectif_vague` — utile pour les membres dont le post a été créé/rempli
    à la main avant l'automatisation, ou rattaché après coup via /membre-lier-thread."""
    try:
        _wave, membre = await resolve_membre_objectif_sync_prepare(db, vague, discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    try:
        contenu = await discord_client.get_thread_starter_content(membre["thread_objectif_id"])
    except discord_client.DiscordAPIError as e:
        raise HTTPException(503, str(e)) from e
    if contenu is None:
        raise HTTPException(404, "Post objectif introuvable sur Discord (fil ou message supprimé).")
    if not contenu:
        raise HTTPException(422, "Post objectif trouvé mais vide (aucun texte ni embed exploitable).")

    updated = await resolve_membre_objectif_sync_apply(db, membre["id"], contenu)
    return MemberOut(**dict(updated))


@router.post("/objectifs-vague/sync", response_model=ObjectifsSyncResponse)
async def post_membres_objectif_sync(vague: int | None = None, db=Depends(get_db)):
    """Synchronise en masse l'objectif de vague de tous les membres ayant un post
    objectif rattaché — un échec individuel (post supprimé, panne Discord ponctuelle)
    n'interrompt pas les suivants, chaque résultat est rapporté séparément."""
    try:
        _wave, cibles = await resolve_membres_objectif_sync_prepare(db, vague)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    resultats: list[ObjectifSyncResultOut] = []
    for m in cibles:
        try:
            contenu = await discord_client.get_thread_starter_content(m["thread_objectif_id"])
        except discord_client.DiscordAPIError as e:
            resultats.append(ObjectifSyncResultOut(discord_id=m["discord_id"], nom=m["nom"], ok=False, message=str(e)))
            continue
        if contenu is None:
            resultats.append(
                ObjectifSyncResultOut(discord_id=m["discord_id"], nom=m["nom"], ok=False, message="Post introuvable sur Discord (fil ou message supprimé).")
            )
            continue
        if not contenu:
            resultats.append(
                ObjectifSyncResultOut(discord_id=m["discord_id"], nom=m["nom"], ok=False, message="Post trouvé mais vide (aucun texte ni embed exploitable).")
            )
            continue
        await resolve_membre_objectif_sync_apply(db, m["id"], contenu)
        resultats.append(
            ObjectifSyncResultOut(discord_id=m["discord_id"], nom=m["nom"], ok=True, message=f"Synchronisé ({len(contenu)} caractères).")
        )

    return ObjectifsSyncResponse(resultats=resultats)


@router.get("/sessions", response_model=SessionsListResponse)
async def get_sessions(
    membre: str | None = None,
    vague: int | None = None,
    semaine: int | None = None,
    statut: str | None = None,
    db=Depends(get_db),
):
    # /sessions-lister côté Discord garde le défaut 50 (tient dans un message) — l'API web
    # n'a pas cette contrainte, donc on relève explicitement la limite ici pour ne pas
    # tronquer silencieusement les listes/agrégats du dashboard CPS Connect.
    try:
        sessions = await resolve_sessions_lister(db, membre, vague, semaine, statut, limit=2000)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return SessionsListResponse(sessions=[SessionOut(**dict(s)) for s in sessions])


@router.get("/binomes", response_model=BinomesResponse)
async def get_binomes(semaine: int | None = None, vague: int | None = None, db=Depends(get_db)):
    try:
        wave, target_semaine, binomes = await resolve_binomes_semaine(db, semaine, vague)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return BinomesResponse(
        wave_id=wave["id"],
        wave_nom=wave["nom"],
        semaine=target_semaine,
        binomes=[BinomeOut(**dict(b)) for b in binomes],
    )


@router.post("/binomes", response_model=BinomeActionResponse)
async def post_binome(body: BinomeDefinirRequest, db=Depends(get_db)):
    """Définit un binôme. Équivalent API de /binome-definir — envoie un DM aux deux
    membres (best-effort, jamais fatal) pour rester cohérent avec le comportement
    Discord existant."""
    try:
        wave, membre_a, membre_b = await resolve_binome_definir(
            db, body.vague, body.semaine, body.membre_a_discord_id, body.membre_b_discord_id
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    dm_echecs = []
    ok_a = await discord_client.send_dm(
        membre_a["discord_id"],
        f"Tu es en binôme avec **{membre_b['nom']}** pour la semaine {body.semaine} "
        f"de la vague **{wave['nom']}**.",
    )
    if not ok_a:
        dm_echecs.append(membre_a["nom"])

    ok_b = await discord_client.send_dm(
        membre_b["discord_id"],
        f"Tu es en binôme avec **{membre_a['nom']}** pour la semaine {body.semaine} "
        f"de la vague **{wave['nom']}**.",
    )
    if not ok_b:
        dm_echecs.append(membre_b["nom"])

    message = f"Binôme semaine {body.semaine} : {membre_a['nom']} ↔ {membre_b['nom']}"
    return BinomeActionResponse(message=message, dm_echecs=dm_echecs)


@router.delete("/binomes", response_model=BinomeActionResponse)
async def delete_binome(
    semaine: int,
    membre_discord_id: str,
    vague: int | None = None,
    db=Depends(get_db),
):
    """Dissout le binôme d'un membre. Équivalent API de /binome-retirer — prévient
    par DM le membre et son partenaire (best-effort), comme côté Discord."""
    try:
        wave, membre, partenaire = await resolve_binome_retirer(db, vague, semaine, membre_discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    dm_echecs = []
    ok = await discord_client.send_dm(
        membre["discord_id"],
        f"Ton binôme de la semaine {semaine} (vague **{wave['nom']}**) a été dissous.",
    )
    if not ok:
        dm_echecs.append(membre["nom"])

    if partenaire is not None:
        ok_partenaire = await discord_client.send_dm(
            partenaire["discord_id"],
            f"Ton binôme de la semaine {semaine} (vague **{wave['nom']}**) a été dissous.",
        )
        if not ok_partenaire:
            dm_echecs.append(partenaire["nom"])

    message = f"Binôme de {membre['nom']} dissous pour la semaine {semaine}."
    return BinomeActionResponse(message=message, dm_echecs=dm_echecs)


@router.post("/sessions", response_model=SessionOut)
async def post_session(body: SessionCreerRequest, db=Depends(get_db)):
    """Crée une session déjà clôturée pour un membre (rattrapage admin). Équivalent
    API de `/session-creer`."""
    try:
        session = await resolve_session_creer(
            db,
            body.vague,
            body.discord_id,
            body.date_session,
            body.creneau,
            body.heure_debut,
            body.heure_fin,
            body.objectif,
            body.bilan,
            body.canal_id,
            body.canal_nom,
            body.blocages,
        )
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return SessionOut(**dict(session))


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def patch_session(session_id: int, body: SessionCorrigerRequest, db=Depends(get_db)):
    """Corrige un champ (objectif, bilan, blocages, creneau) d'une session existante.
    Équivalent API de `/session-corriger` côté admin — pas de vérification de
    propriétaire, un admin peut corriger n'importe quelle session."""
    try:
        session = await resolve_session_corriger(db, session_id, body.champ, body.valeur)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return SessionOut(**dict(session))


@router.delete("/sessions/{session_id}", response_model=SessionSupprimerResponse)
async def delete_session_endpoint(session_id: int, db=Depends(get_db)):
    """Supprime une session. Équivalent API de `/session-corriger champ:suppression`."""
    try:
        await resolve_session_supprimer(db, session_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return SessionSupprimerResponse(id=session_id, message=f"Session {session_id} supprimée.")


def _configured_ai_providers() -> list[str]:
    """Providers dont la clé API est présente dans le .env — jamais la clé elle-même,
    juste sa présence, pour prévenir l'admin avant qu'il sélectionne un provider sans
    clé configurée sur le serveur."""
    configured = []
    if ANTHROPIC_API_KEY:
        configured.append("anthropic")
    if GROQ_API_KEY:
        configured.append("groq")
    return configured


def _bilan_texte_out(bilan, poste_discord: bool | None = None) -> BilanTexteOut | None:
    if bilan is None:
        return None
    return BilanTexteOut(
        texte=bilan["texte"],
        ecrit_par_discord_id=bilan["ecrit_par_discord_id"],
        updated_at=bilan["updated_at"],
        poste_discord=poste_discord,
    )


@router.get("/bilans-semaine", response_model=BilansSemaineListResponse)
async def get_bilans_semaine_endpoint(semaine: int, vague: int | None = None, db=Depends(get_db)):
    """Liste, pour chaque membre de la vague, son bilan hebdo de la semaine donnée
    (texte à None si pas encore rédigé) — vue d'ensemble admin, cf. bilan-semaine
    ci-dessous pour lire/écrire le bilan d'un seul membre."""
    try:
        wave, rows = await resolve_bilans_semaine_lister(db, vague, semaine)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return BilansSemaineListResponse(
        wave_nom=wave["nom"],
        semaine=semaine,
        bilans=[
            BilanMembreOut(
                discord_id=r["discord_id"],
                nom=r["nom"],
                texte=r["texte"],
                ecrit_par_discord_id=r["ecrit_par_discord_id"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ],
    )


@router.get("/bilans-vague", response_model=BilansVagueListResponse)
async def get_bilans_vague_endpoint(vague: int | None = None, db=Depends(get_db)):
    """Liste, pour chaque membre de la vague, son bilan de synthèse de vague (texte à
    None si pas encore rédigé) — équivalent de bilans-semaine, sans filtre semaine."""
    try:
        wave, rows = await resolve_bilans_vague_lister(db, vague)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    return BilansVagueListResponse(
        wave_nom=wave["nom"],
        bilans=[
            BilanMembreOut(
                discord_id=r["discord_id"],
                nom=r["nom"],
                texte=r["texte"],
                ecrit_par_discord_id=r["ecrit_par_discord_id"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ],
    )


@router.get("/members/{discord_id}/bilan-semaine", response_model=BilanTexteOut | None)
async def get_bilan_semaine_endpoint(
    discord_id: str, semaine: int, vague: int | None = None, db=Depends(get_db)
):
    """Bilan hebdomadaire rédigé à la main par l'admin pour ce membre — distinct du
    résumé informatif de `/members/{discord_id}/bilan` (non stocké, calculé à la volée)."""
    try:
        _wave, bilan = await resolve_bilan_semaine_lire(db, vague, discord_id, semaine)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return _bilan_texte_out(bilan)


@router.put("/members/{discord_id}/bilan-semaine", response_model=BilanTexteOut)
async def put_bilan_semaine_endpoint(
    discord_id: str,
    body: BilanTexteRequest,
    semaine: int,
    vague: int | None = None,
    db=Depends(get_db),
    caller_id: str = Depends(get_caller_discord_id),
):
    """Écrit (upsert) le bilan hebdomadaire d'un membre. Réservé aux admins (gate du
    router) — `ecrit_par` = l'admin appelant. Si `body.poster` (défaut True) et qu'un
    post objectif est rattaché, poste aussi le bilan en réponse dans ce fil Discord —
    best-effort, un échec de post n'invalide jamais l'enregistrement (cf. `poste_discord`
    dans la réponse pour signaler le résultat à l'UI)."""
    try:
        wave, bilan, membre = await resolve_bilan_semaine_ecrire(db, vague, discord_id, semaine, body.valeur, caller_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    poste_discord = None
    if body.poster:
        thread_id = membre["thread_objectif_id"]
        if thread_id:
            texte_discord = f"**Bilan hebdomadaire — {membre['nom']} — vague {wave['nom']}, semaine {semaine}**\n\n{body.valeur}"
            poste_discord = await discord_client.post_channel_message(thread_id, texte_discord)
        else:
            poste_discord = False

    return _bilan_texte_out(bilan, poste_discord)


@router.get("/members/{discord_id}/bilan-vague", response_model=BilanTexteOut | None)
async def get_bilan_vague_endpoint(discord_id: str, vague: int | None = None, db=Depends(get_db)):
    """Bilan de synthèse de vague rédigé à la main par l'admin pour ce membre."""
    try:
        _wave, bilan = await resolve_bilan_vague_lire(db, vague, discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return _bilan_texte_out(bilan)


@router.put("/members/{discord_id}/bilan-vague", response_model=BilanTexteOut)
async def put_bilan_vague_endpoint(
    discord_id: str,
    body: BilanTexteRequest,
    vague: int | None = None,
    db=Depends(get_db),
    caller_id: str = Depends(get_caller_discord_id),
):
    """Écrit (upsert) le bilan de synthèse de vague d'un membre."""
    try:
        _wave, bilan = await resolve_bilan_vague_ecrire(db, vague, discord_id, body.valeur, caller_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e
    return _bilan_texte_out(bilan)


@router.post("/members/{discord_id}/bilan-semaine/suggerer", response_model=BilanSuggestionResponse)
async def post_bilan_semaine_suggerer(discord_id: str, semaine: int, vague: int | None = None, db=Depends(get_db)):
    """Génère un brouillon de bilan hebdomadaire via le provider IA configuré (onglet
    Paramètres), à partir des vraies sessions du membre pour cette semaine — jamais
    sauvegardé automatiquement, c'est à l'admin de relire/corriger puis d'appeler
    PUT bilan-semaine. 403 si l'assistant IA est désactivé."""
    settings = await resolve_ai_settings_lire(db)
    if not settings["enabled"]:
        raise HTTPException(403, "Assistant IA désactivé (onglet Paramètres).")

    try:
        wave, membre = await resolve_wave_et_membre(db, vague, discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    prompt = await build_bilan_semaine_prompt(db, membre, wave, semaine)
    try:
        suggestion = await ai_provider.generate_suggestion(settings["provider"], settings["model"], prompt)
    except ai_provider.AIProviderError as e:
        raise HTTPException(503, str(e)) from e
    return BilanSuggestionResponse(suggestion=suggestion)


@router.post("/members/{discord_id}/bilan-vague/suggerer", response_model=BilanSuggestionResponse)
async def post_bilan_vague_suggerer(discord_id: str, vague: int | None = None, db=Depends(get_db)):
    """Génère un brouillon de bilan de vague via le provider IA configuré, à partir des
    bilans hebdo déjà rédigés par l'admin et des sessions de toute la vague. 403 si
    l'assistant IA est désactivé."""
    settings = await resolve_ai_settings_lire(db)
    if not settings["enabled"]:
        raise HTTPException(403, "Assistant IA désactivé (onglet Paramètres).")

    try:
        wave, membre = await resolve_wave_et_membre(db, vague, discord_id)
    except ResolutionError as e:
        raise HTTPException(404, str(e)) from e

    prompt = await build_bilan_vague_prompt(db, membre, wave)
    try:
        suggestion = await ai_provider.generate_suggestion(settings["provider"], settings["model"], prompt)
    except ai_provider.AIProviderError as e:
        raise HTTPException(503, str(e)) from e
    return BilanSuggestionResponse(suggestion=suggestion)


@router.get("/ai-settings", response_model=AiSettingsOut)
async def get_ai_settings_endpoint(db=Depends(get_db)):
    settings = await resolve_ai_settings_lire(db)
    return AiSettingsOut(**dict(settings), configured_providers=_configured_ai_providers())


@router.put("/ai-settings", response_model=AiSettingsOut)
async def put_ai_settings_endpoint(
    body: AiSettingsRequest, db=Depends(get_db), caller_id: str = Depends(get_caller_discord_id)
):
    try:
        settings = await resolve_ai_settings_ecrire(db, body.enabled, body.provider, body.model, caller_id)
    except ResolutionError as e:
        raise HTTPException(400, str(e)) from e
    return AiSettingsOut(**dict(settings), configured_providers=_configured_ai_providers())


@router.get("/ai-settings/models", response_model=AiModelsResponse)
async def get_ai_models_endpoint(provider: str):
    """Liste les modèles réellement disponibles pour ce provider (clé du serveur) —
    évite de figer une liste en dur côté frontend, qui devient vite obsolète (cf.
    dépréciations Groq fréquentes)."""
    try:
        models = await ai_provider.list_models(provider)
    except ai_provider.AIProviderError as e:
        raise HTTPException(503, str(e)) from e
    return AiModelsResponse(provider=provider, models=sorted(models))
