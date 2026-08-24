from typing import Literal

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: int
    date: str
    creneau: str
    statut: str
    debut: str
    fin: str | None
    objectif: str
    bilan: str | None
    blocages: str | None
    canal_nom: str | None = None
    wave_nom: str | None = None
    membre_nom: str | None = None


class AccessResponse(BaseModel):
    is_participant: bool
    is_admin: bool


class JournalResponse(BaseModel):
    nom: str
    label: str
    show_wave: bool
    sessions: list[SessionOut]


class BinomeJournalResponse(BaseModel):
    partenaire_nom: str
    partenaire_discord_id: str
    label: str
    sessions: list[SessionOut]


class BilanResponse(BaseModel):
    nom: str
    label: str
    nb_sessions: int
    nb_completes: int
    nb_incompletes: int
    duree_totale: str
    blocages: list[str]


class BilanTexteRequest(BaseModel):
    valeur: str


class BilanTexteOut(BaseModel):
    texte: str
    ecrit_par_discord_id: str
    updated_at: str


class BilanMembreOut(BaseModel):
    discord_id: str
    nom: str
    texte: str | None
    ecrit_par_discord_id: str | None
    updated_at: str | None


class BilansSemaineListResponse(BaseModel):
    wave_nom: str
    semaine: int
    bilans: list[BilanMembreOut]


class MemberOut(BaseModel):
    id: int
    discord_id: str
    nom: str
    profil: str
    certif_ou_projet: str | None
    objectif_vague: str | None = None
    thread_objectif_id: str | None = None


class ObjectifSyncResultOut(BaseModel):
    discord_id: str
    nom: str
    ok: bool
    message: str


class ObjectifsSyncResponse(BaseModel):
    resultats: list[ObjectifSyncResultOut]


class MembersResponse(BaseModel):
    wave_id: int
    wave_nom: str
    membres: list[MemberOut]


class BinomeOut(BaseModel):
    membre_a: int
    nom_a: str
    membre_b: int
    nom_b: str


class BinomesResponse(BaseModel):
    wave_id: int
    wave_nom: str
    semaine: int
    binomes: list[BinomeOut]


class SessionsListResponse(BaseModel):
    sessions: list[SessionOut]


class VagueOut(BaseModel):
    id: int
    nom: str
    active: bool


class VaguesResponse(BaseModel):
    vagues: list[VagueOut]


class SessionCorrigerRequest(BaseModel):
    champ: Literal["objectif", "bilan", "blocages", "creneau"]
    valeur: str


class SessionSupprimerResponse(BaseModel):
    id: int
    message: str


class BinomeDefinirRequest(BaseModel):
    semaine: int
    membre_a_discord_id: str
    membre_b_discord_id: str
    vague: int | None = None


class BinomeActionResponse(BaseModel):
    message: str
    dm_echecs: list[str] = []


class MembreAjouterRequest(BaseModel):
    discord_id: str
    nom: str
    profil: str
    certif_ou_projet: str | None = None
    vague: int | None = None


class MembreAjouterResponse(BaseModel):
    id: int
    discord_id: str
    nom: str
    profil: str
    certif_ou_projet: str | None
    dm_ok: bool


class MembreEditerRequest(BaseModel):
    champ: Literal["nom", "profil", "certif_ou_projet", "objectif_vague"]
    valeur: str
    vague: int | None = None


class DiscordMemberOut(BaseModel):
    discord_id: str
    username: str


class DiscordMembersResponse(BaseModel):
    members: list[DiscordMemberOut]


class DiscordVoiceChannelOut(BaseModel):
    channel_id: str
    name: str


class DiscordVoiceChannelsResponse(BaseModel):
    channels: list[DiscordVoiceChannelOut]


class VagueAdminOut(BaseModel):
    id: int
    nom: str
    date_debut: str
    date_fin: str
    statut: str


class VaguesListResponse(BaseModel):
    vagues: list[VagueAdminOut]


class VagueCreerRequest(BaseModel):
    nom: str
    date_debut: str  # AAAA-MM-JJ (ISO), parsé côté endpoint
    date_fin: str


class SalonOut(BaseModel):
    canal_id: str
    canal_nom: str
    actif: bool
    wave_nom: str


class SalonsListResponse(BaseModel):
    salons: list[SalonOut]


class SalonAjouterRequest(BaseModel):
    canal_id: str
    canal_nom: str
    vague: int | None = None


class ObjectifVagueRequest(BaseModel):
    valeur: str


class MembreLierThreadRequest(BaseModel):
    lien_ou_id: str
    vague: int | None = None


class SessionCreerRequest(BaseModel):
    discord_id: str
    date_session: str  # AAAA-MM-JJ
    creneau: str
    heure_debut: str  # HH:MM
    heure_fin: str | None = None  # HH:MM
    objectif: str | None = None
    bilan: str | None = None
    canal_id: str | None = None
    canal_nom: str | None = None
    blocages: str | None = None
    vague: int | None = None
