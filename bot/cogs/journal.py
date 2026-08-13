from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import TZ
from bot.db.database import get_connection
from bot.db.binomes import get_partner_id
from bot.db.members import get_member, get_member_all_waves, get_member_by_id, update_objectif
from bot.db.sessions import list_by_member_ids_and_semaine, list_by_member_week
from bot.db.waves import get_active_wave, get_wave_by_id, list_waves
from bot.services.weeks import week_number_for_date


def _format_session_line(s, show_wave: bool = False) -> str:
    duree = ""
    if s["fin"]:
        debut = datetime.fromisoformat(s["debut"])
        fin = datetime.fromisoformat(s["fin"])
        duree = f" ({str(fin - debut).split('.')[0]})"
    statut = s["statut"]
    entete = f"**#{s['id']} · {s['date']} · {s['creneau']}**"
    if show_wave:
        entete += f" · {s['wave_nom']}"
    lignes = [
        f"{entete} — {statut}{duree}",
        f"Objectif : {s['objectif']}",
    ]
    if s["bilan"]:
        lignes.append(f"Bilan : {s['bilan']}")
    if s["blocages"]:
        lignes.append(f"Blocages : {s['blocages']}")
    return "\n".join(lignes)


def _format_journal(nom: str, label: str, sessions: list, show_wave: bool = False) -> str:
    if not sessions:
        return f"**Journal de {nom} — {label}**\nAucune session enregistrée."
    corps = "\n\n".join(_format_session_line(s, show_wave) for s in sessions)
    return f"**Journal de {nom} — {label}**\n\n{corps}"


async def _wave_autocomplete(db, current: str) -> list[app_commands.Choice[int]]:
    waves = await list_waves(db)
    choices = []
    for w in waves:
        label = f"#{w['id']} · {w['nom']} ({w['statut']}) · {w['date_debut']} → {w['date_fin']}"
        if current and current.lower() not in label.lower():
            continue
        choices.append(app_commands.Choice(name=label[:100], value=w["id"]))
    return choices[:25]


class ResolutionError(Exception):
    pass


async def _resolve_member_sessions(db, discord_id: str, vague_id: int | None, semaine: int | None):
    """Résout (sessions, nom_affiché, label, show_wave) selon la règle :
    - ni vague ni semaine -> vague active + semaine courante
    - semaine seul (sans vague) -> recherche à travers toutes les vagues
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
        return sessions, member["nom"], f"vague {wave['nom']}, semaine {target_semaine}", False

    if vague_id is None and semaine is not None:
        members = await get_member_all_waves(db, discord_id)
        if not members:
            raise ResolutionError("Tu n'es enregistré dans aucune vague.")
        member_ids = [m["id"] for m in members]
        sessions = await list_by_member_ids_and_semaine(db, member_ids, semaine)
        return sessions, members[0]["nom"], f"semaine {semaine} (toutes vagues)", True

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
    return sessions, member["nom"], f"vague {wave['nom']}, semaine {target_semaine}", False


class ObjectifVagueModal(discord.ui.Modal, title="Objectif de vague"):
    def __init__(self, objectif_actuel: str | None):
        super().__init__()
        self.objectif = discord.ui.TextInput(
            label="Ton objectif pour toute la vague",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=objectif_actuel or "",
        )
        self.add_item(self.objectif)

    async def on_submit(self, interaction: discord.Interaction):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    "Tu n'es pas enregistré comme membre de la vague active.", ephemeral=True
                )
                return

            await update_objectif(db, member["id"], str(self.objectif))

        await interaction.response.send_message(
            f"Objectif de vague mis à jour : {self.objectif}", ephemeral=True
        )


class JournalCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mon-journal", description="Affiche tes sessions")
    async def mon_journal(
        self,
        interaction: discord.Interaction,
        vague: int | None = None,
        semaine: int | None = None,
    ):
        async with get_connection() as db:
            try:
                sessions, nom, label, show_wave = await _resolve_member_sessions(
                    db, str(interaction.user.id), vague, semaine
                )
            except ResolutionError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

            texte = _format_journal(nom, label, sessions, show_wave)
            await interaction.response.send_message(texte, ephemeral=True)

    @mon_journal.autocomplete("vague")
    async def mon_journal_vague_autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_connection() as db:
            return await _wave_autocomplete(db, current)

    @app_commands.command(
        name="binome-journal", description="Affiche le journal de ton binôme"
    )
    async def binome_journal(
        self,
        interaction: discord.Interaction,
        vague: int | None = None,
        semaine: int | None = None,
    ):
        async with get_connection() as db:
            if vague is not None:
                wave = await get_wave_by_id(db, vague)
                if wave is None:
                    await interaction.response.send_message("Vague introuvable.", ephemeral=True)
                    return
            else:
                if semaine is not None:
                    all_waves = await list_waves(db)
                    if len(all_waves) > 1:
                        await interaction.response.send_message(
                            "Plusieurs vagues existent — précise le paramètre `vague` pour lever l'ambiguïté.",
                            ephemeral=True,
                        )
                        return
                wave = await get_active_wave(db)
                if wave is None:
                    await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                    return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    f"Tu n'es pas enregistré comme membre de la vague **{wave['nom']}**.", ephemeral=True
                )
                return

            if semaine is not None:
                target_semaine = semaine
            else:
                wave_start = datetime.fromisoformat(wave["date_debut"]).date()
                target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)

            partner_id = await get_partner_id(db, member["id"], wave["id"], target_semaine)
            if partner_id is None:
                await interaction.response.send_message(
                    f"Tu étais en solo pour la semaine {target_semaine} (vague {wave['nom']}) — pas de binôme défini.",
                    ephemeral=True,
                )
                return

            partner = await get_member_by_id(db, partner_id)
            sessions = await list_by_member_week(db, partner_id, wave["id"], target_semaine)
            texte = _format_journal(
                partner["nom"], f"vague {wave['nom']}, semaine {target_semaine}", sessions
            )
            await interaction.response.send_message(
                f"(Lecture seule — journal de ton binôme)\n\n{texte}", ephemeral=True
            )

    @binome_journal.autocomplete("vague")
    async def binome_journal_vague_autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_connection() as db:
            return await _wave_autocomplete(db, current)

    @app_commands.command(
        name="bilan-semaine", description="Génère le bilan hebdomadaire agrégé"
    )
    async def bilan_semaine(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
        vague: int | None = None,
        semaine: int | None = None,
    ):
        is_admin = any(r.name == "Admin SkillUp" for r in interaction.user.roles)
        if membre is not None and not is_admin:
            await interaction.response.send_message(
                "Seuls les admins peuvent consulter le bilan d'un autre membre.",
                ephemeral=True,
            )
            return

        target_discord_id = str(membre.id) if membre else str(interaction.user.id)

        async with get_connection() as db:
            try:
                sessions, nom, label, show_wave = await _resolve_member_sessions(
                    db, target_discord_id, vague, semaine
                )
            except ResolutionError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

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

            texte = (
                f"**Bilan hebdomadaire — {nom} — {label}**\n\n"
                f"Sessions : {nb_sessions} ({nb_completes} complètes, {nb_incompletes} incomplètes)\n"
                f"Temps total : {duree_totale}\n"
            )
            if blocages:
                texte += "\nBlocages rencontrés :\n" + "\n".join(f"- {b}" for b in blocages)
            else:
                texte += "\nAucun blocage signalé."

            await interaction.response.send_message(texte, ephemeral=True)

    @bilan_semaine.autocomplete("vague")
    async def bilan_semaine_vague_autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_connection() as db:
            return await _wave_autocomplete(db, current)

    @app_commands.command(
        name="objectif-vague", description="Définit ou met à jour ton objectif global de vague"
    )
    async def objectif_vague(self, interaction: discord.Interaction):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    "Tu n'es pas enregistré comme membre de la vague active.", ephemeral=True
                )
                return

            objectif_actuel = member["objectif_vague"]

        await interaction.response.send_modal(ObjectifVagueModal(objectif_actuel))


async def setup(bot: commands.Bot):
    await bot.add_cog(JournalCog(bot))
