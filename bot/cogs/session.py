from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import CRENEAUX, TZ
from bot.db.database import get_connection
from bot.db.coworking_channels import is_coworking_channel
from bot.db.members import get_member
from bot.db.sessions import (
    delete_session,
    end_session,
    get_by_id,
    get_open_session,
    list_recent_by_member,
    start_session,
    update_field,
)
from bot.db.waves import get_active_wave
from bot.services.weeks import week_number_for_date


class SessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="session-start", description="Démarre une session de coworking")
    @app_commands.choices(
        creneau=[app_commands.Choice(name=c, value=c) for c in CRENEAUX]
    )
    async def session_start(
        self, interaction: discord.Interaction, creneau: app_commands.Choice[str], objectif: str
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message(
                    "Aucune vague active. Contacte un admin.", ephemeral=True
                )
                return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    "Tu n'es pas enregistré comme membre de la vague active. Contacte un admin.",
                    ephemeral=True,
                )
                return

            if await get_open_session(db, member["id"]):
                await interaction.response.send_message(
                    "Tu as déjà une session ouverte. Clôture-la avec `/session-end` avant d'en démarrer une nouvelle.",
                    ephemeral=True,
                )
                return

            voice_state = interaction.user.voice
            if voice_state is None or voice_state.channel is None:
                await interaction.response.send_message(
                    "Rejoins un salon de coworking avant de démarrer ta session.", ephemeral=True
                )
                return

            channel = voice_state.channel
            if not await is_coworking_channel(db, str(channel.id)):
                await interaction.response.send_message(
                    "Rejoins un salon de coworking avant de démarrer ta session.", ephemeral=True
                )
                return

            now = datetime.now(TZ)
            today = now.date()
            semaine = week_number_for_date(today, datetime.fromisoformat(wave["date_debut"]).date())

            await start_session(
                db,
                member_id=member["id"],
                wave_id=wave["id"],
                semaine=semaine,
                session_date=today,
                creneau=creneau.value,
                canal_id=str(channel.id),
                canal_nom=channel.name,
                debut=now,
                objectif=objectif,
            )

            await interaction.response.send_message(
                f"{interaction.user.mention} démarre une session — créneau **{creneau.value}**, "
                f"salon **{channel.name}**.\nObjectif : {objectif}"
            )

    @app_commands.command(name="session-end", description="Clôture ta session en cours")
    async def session_end(
        self, interaction: discord.Interaction, bilan: str, blocages: str | None = None
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message(
                    "Aucune vague active.", ephemeral=True
                )
                return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    "Tu n'es pas enregistré comme membre de la vague active.", ephemeral=True
                )
                return

            open_session = await get_open_session(db, member["id"])
            if open_session is None:
                await interaction.response.send_message(
                    "Tu n'as pas de session ouverte.", ephemeral=True
                )
                return

            now = datetime.now(TZ)
            await end_session(db, open_session["id"], now, bilan, blocages)

            debut = datetime.fromisoformat(open_session["debut"])
            duree = now - debut
            duree_str = str(duree).split(".")[0]

            texte = f"{interaction.user.mention} clôture sa session — durée **{duree_str}**.\nBilan : {bilan}"
            if blocages:
                texte += f"\nBlocages : {blocages}"
            await interaction.response.send_message(
                texte,
            )

    @app_commands.command(
        name="session-corriger", description="Corrige ou supprime une session saisie par erreur"
    )
    @app_commands.choices(
        champ=[
            app_commands.Choice(name=c, value=c)
            for c in ("objectif", "bilan", "blocages", "creneau", "suppression")
        ]
    )
    async def session_corriger(
        self,
        interaction: discord.Interaction,
        id_session: int,
        champ: app_commands.Choice[str],
        valeur: str | None = None,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            session = await get_by_id(db, id_session)
            if session is None:
                await interaction.response.send_message("Session introuvable.", ephemeral=True)
                return

            member = await get_member(db, str(interaction.user.id), wave["id"])
            is_admin = any(r.name == "Admin SkillUp" for r in interaction.user.roles)
            if not is_admin and (member is None or session["member_id"] != member["id"]):
                await interaction.response.send_message(
                    "Tu ne peux corriger que tes propres sessions.", ephemeral=True
                )
                return

            if champ.value == "suppression":
                await delete_session(db, id_session)
                await interaction.response.send_message(
                    f"Session {id_session} supprimée.", ephemeral=True
                )
                return

            if valeur is None:
                await interaction.response.send_message(
                    "Le paramètre `valeur` est requis pour ce champ.", ephemeral=True
                )
                return

            if champ.value == "creneau" and valeur not in CRENEAUX:
                await interaction.response.send_message(
                    f"Créneau invalide. Valeurs possibles : {', '.join(CRENEAUX)}", ephemeral=True
                )
                return

            await update_field(db, id_session, champ.value, valeur)
            await interaction.response.send_message(
                f"Session {id_session} mise à jour — `{champ.value}` → {valeur}", ephemeral=True
            )

    @session_corriger.autocomplete("id_session")
    async def session_corriger_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                return []

            member = await get_member(db, str(interaction.user.id), wave["id"])
            if member is None:
                return []

            sessions = await list_recent_by_member(db, member["id"], limit=25)

        choices = []
        for s in sessions:
            label = f"#{s['id']} · {s['date']} · {s['creneau']} · {s['objectif'][:40]}"
            if current and current not in str(s["id"]) and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=s["id"]))
        return choices[:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(SessionCog(bot))
