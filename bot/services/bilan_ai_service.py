"""Construction des prompts pour la suggestion IA de bilans (hebdo/vague) — fonctions
pures, indépendantes du client HTTP Anthropic (cf. api/anthropic_client.py, appelé
côté routeur). Toujours instruire le modèle de ne rien inventer : la matière vient
uniquement des sessions/bilans déjà en base."""

from bot.db.bilans import list_bilans_semaine_by_member
from bot.db.sessions import list_by_member_wave, list_by_member_week

_CONSIGNE = (
    "Tu es un assistant qui aide un animateur de coworking à rédiger un bilan. "
    "Rédige en français, ton factuel et concis, format à puces courtes. "
    "N'invente RIEN : base-toi uniquement sur les informations fournies ci-dessous. "
    "Si les données sont insuffisantes, dis-le explicitement plutôt que de combler les trous. "
    "Ne rédige QUE le texte du bilan, sans préambule ni signature."
)


def _format_sessions(sessions) -> str:
    if not sessions:
        return "(aucune session enregistrée)"
    lignes = []
    for s in sessions:
        lignes.append(f"- Semaine {s['semaine']}, {s['date']} ({s['creneau']}, statut {s['statut']})")
        if s["objectif"]:
            lignes.append(f"  Objectif : {s['objectif']}")
        if s["bilan"]:
            lignes.append(f"  Bilan : {s['bilan']}")
        if s["blocages"]:
            lignes.append(f"  Blocages : {s['blocages']}")
    return "\n".join(lignes)


async def build_bilan_semaine_prompt(db, member, wave, semaine: int) -> str:
    sessions = await list_by_member_week(db, member["id"], wave["id"], semaine)
    objectif_vague = member["objectif_vague"] or "(non défini)"
    return (
        f"{_CONSIGNE}\n\n"
        f"Membre : {member['nom']}\n"
        f"Objectif de vague : {objectif_vague}\n"
        f"Vague : {wave['nom']}, semaine {semaine}\n\n"
        f"Sessions de coworking de la semaine :\n{_format_sessions(sessions)}\n\n"
        f"Rédige le bilan hebdomadaire de {member['nom']} pour la semaine {semaine}."
    )


async def build_bilan_vague_prompt(db, member, wave) -> str:
    bilans_semaine = await list_bilans_semaine_by_member(db, member["id"], wave["id"])
    sessions = await list_by_member_wave(db, member["id"], wave["id"])
    objectif_vague = member["objectif_vague"] or "(non défini)"

    if bilans_semaine:
        historique = "\n".join(f"- Semaine {b['semaine']} : {b['texte']}" for b in bilans_semaine)
    else:
        historique = "(aucun bilan hebdomadaire rédigé pour l'instant)"

    return (
        f"{_CONSIGNE}\n\n"
        f"Membre : {member['nom']}\n"
        f"Objectif de vague : {objectif_vague}\n"
        f"Vague : {wave['nom']}\n\n"
        f"Bilans hebdomadaires déjà rédigés par l'admin :\n{historique}\n\n"
        f"Sessions de coworking de toute la vague :\n{_format_sessions(sessions)}\n\n"
        f"Rédige le bilan de synthèse de toute la vague pour {member['nom']}, en te basant "
        f"prioritairement sur les bilans hebdomadaires ci-dessus (ce sont des synthèses déjà "
        f"validées par l'admin) et en complétant avec les sessions si besoin."
    )
