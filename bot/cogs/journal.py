from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import TZ
from bot.db.database import get_connection
from bot.db.binomes import get_partner_id
from bot.db.members import get_member, get_member_by_id, update_objectif
from bot.db.sessions import list_by_member_week
from bot.db.waves import get_active_wave
from bot.services.weeks import week_number_for_date


def _format_session_line(s) -> str:
    duree = ""
    if s["fin"]:
        debut = datetime.fromisoformat(s["debut"])
        fin = datetime.fromisoformat(s["fin"])
        duree = f" ({str(fin - debut).split('.')[0]})"
    statut = s["statut"]
    lignes = [
        f"**#{s['id']} · {s['date']} · {s['creneau']}** — {statut}{duree}",
        f"Objectif : {s['objectif']}",
    ]
    if s["bilan"]:
        lignes.append(f"Bilan : {s['bilan']}")
    if s["blocages"]:
        lignes.append(f"Blocages : {s['blocages']}")
    return "\n".join(lignes)


def _format_journal(nom: str, semaine: int, sessions: list) -> str:
    if not sessions:
        return f"**Journal de {nom} — semaine {semaine}**\nAucune session enregistrée."
    corps = "\n\n".join(_format_session_line(s) for s in sessions)
    return f"**Journal de {nom} — semaine {semaine}**\n\n{corps}"


class JournalCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mon-journal", description="Affiche tes sessions de la semaine")
    async def mon_journal(self, interaction: discord.Interaction, semaine: int | None = None):
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

            wave_start = datetime.fromisoformat(wave["date_debut"]).date()
            target_semaine = semaine or week_number_for_date(datetime.now(TZ).date(), wave_start)

            sessions = await list_by_member_week(db, member["id"], wave["id"], target_semaine)
            texte = _format_journal(member["nom"], target_semaine, sessions)
            await interaction.response.send_message(texte, ephemeral=True)

    @app_commands.command(
        name="binome-journal", description="Affiche le journal de ton binôme de la semaine"
    )
    async def binome_journal(self, interaction: discord.Interaction, semaine: int | None = None):
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

            wave_start = datetime.fromisoformat(wave["date_debut"]).date()
            target_semaine = semaine or week_number_for_date(datetime.now(TZ).date(), wave_start)

            partner_id = await get_partner_id(db, member["id"], wave["id"], target_semaine)
            if partner_id is None:
                await interaction.response.send_message(
                    f"Tu étais en solo pour la semaine {target_semaine} — pas de binôme défini.",
                    ephemeral=True,
                )
                return

            partner = await get_member_by_id(db, partner_id)
            sessions = await list_by_member_week(db, partner_id, wave["id"], target_semaine)
            texte = _format_journal(partner["nom"], target_semaine, sessions)
            await interaction.response.send_message(
                f"(Lecture seule — journal de ton binôme)\n\n{texte}", ephemeral=True
            )

    @app_commands.command(
        name="bilan-semaine", description="Génère le bilan hebdomadaire agrégé"
    )
    async def bilan_semaine(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
        semaine: int | None = None,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            is_admin = any(r.name == "Admin SkillUp" for r in interaction.user.roles)
            if membre is not None and not is_admin:
                await interaction.response.send_message(
                    "Seuls les admins peuvent consulter le bilan d'un autre membre.",
                    ephemeral=True,
                )
                return

            target_discord_id = str(membre.id) if membre else str(interaction.user.id)
            member = await get_member(db, target_discord_id, wave["id"])
            if member is None:
                await interaction.response.send_message(
                    "Membre non enregistré dans la vague active.", ephemeral=True
                )
                return

            wave_start = datetime.fromisoformat(wave["date_debut"]).date()
            target_semaine = semaine or week_number_for_date(datetime.now(TZ).date(), wave_start)

            sessions = await list_by_member_week(db, member["id"], wave["id"], target_semaine)

            nb_sessions = len(sessions)
            nb_completes = sum(1 for s in sessions if s["statut"] == "complète")
            nb_incompletes = sum(1 for s in sessions if s["statut"] == "incomplète")
            duree_totale = None
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
                f"**Bilan hebdomadaire — {member['nom']} — semaine {target_semaine}**\n\n"
                f"Sessions : {nb_sessions} ({nb_completes} complètes, {nb_incompletes} incomplètes)\n"
                f"Temps total : {duree_totale}\n"
            )
            if blocages:
                texte += "\nBlocages rencontrés :\n" + "\n".join(f"- {b}" for b in blocages)
            else:
                texte += "\nAucun blocage signalé."

            await interaction.response.send_message(texte, ephemeral=True)

    @app_commands.command(
        name="objectif-vague", description="Définit ou met à jour ton objectif global de vague"
    )
    async def objectif_vague(self, interaction: discord.Interaction, objectif: str):
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

            await update_objectif(db, member["id"], objectif)
            await interaction.response.send_message(
                f"Objectif de vague mis à jour : {objectif}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(JournalCog(bot))
