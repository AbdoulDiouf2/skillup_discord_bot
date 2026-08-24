import re
from datetime import datetime, timedelta

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
    get_recent_incomplete_session,
    list_distinct_creneaux,
    list_recent_by_member,
    start_session,
    update_field,
)
from bot.db.waves import get_active_wave
from bot.services.weeks import week_number_for_date

CRENEAU_FORMAT = re.compile(r"\d{1,2}h-\d{1,2}h")

# Fenêtre pendant laquelle /session-end peut encore rattraper une session auto-clôturée
# par la RG-16 (débordement sur minuit) — au-delà, on considère la session vraiment oubliée.
RATTRAPAGE_FENETRE = timedelta(hours=4)


def _sort_creneaux(creneaux: set[str]) -> list[str]:
    def sort_key(c: str) -> int:
        m = re.match(r"\d{1,2}", c)
        return int(m.group()) if m else 0

    return sorted(creneaux, key=sort_key)


async def _require_coworking_channel(
    interaction: discord.Interaction, db, wave_id: int, verbe: str
) -> discord.abc.GuildChannel | None:
    """Vérifie que le membre est dans un salon vocal de coworking reconnu et que la
    commande a été lancée dans le fil de discussion de ce même salon (RG-12)."""
    voice_state = interaction.user.voice
    if voice_state is None or voice_state.channel is None:
        await interaction.response.send_message(
            f"Rejoins un salon de coworking avant de {verbe} ta session.", ephemeral=True
        )
        return None

    channel = voice_state.channel
    if not await is_coworking_channel(db, str(channel.id), wave_id):
        await interaction.response.send_message(
            f"Rejoins un salon de coworking avant de {verbe} ta session.", ephemeral=True
        )
        return None

    if interaction.channel_id != channel.id:
        await interaction.response.send_message(
            f"Lance la commande dans le fil de discussion du salon **{channel.name}** "
            f"(celui où tu es connecté).",
            ephemeral=True,
        )
        return None

    return channel


class SessionStartModal(discord.ui.Modal, title="Démarrer une session"):
    objectif = discord.ui.TextInput(
        label="Objectif de la session",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, creneau: str):
        super().__init__()
        self.creneau = creneau

    async def on_submit(self, interaction: discord.Interaction):
        if not CRENEAU_FORMAT.fullmatch(self.creneau):
            await interaction.response.send_message(
                "Créneau invalide — format attendu `HHh-HHh` (ex. 19h-21h).", ephemeral=True
            )
            return

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

            channel = await _require_coworking_channel(interaction, db, wave["id"], "démarrer")
            if channel is None:
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
                creneau=self.creneau,
                canal_id=str(channel.id),
                canal_nom=channel.name,
                debut=now,
                objectif=str(self.objectif),
            )

            await interaction.response.send_message(
                f"{interaction.user.mention} démarre une session — créneau **{self.creneau}**, "
                f"salon **{channel.name}**.\nObjectif : {self.objectif}"
            )


class SessionEndModal(discord.ui.Modal, title="Clôturer ta session"):
    bilan = discord.ui.TextInput(
        label="Bilan — qu'as-tu fait ?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )
    blocages = discord.ui.TextInput(
        label="Blocages (optionnel)",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        now = datetime.now(TZ)
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

            open_session = await get_open_session(db, member["id"])
            rattrapage = open_session is None
            if rattrapage:
                open_session = await get_recent_incomplete_session(
                    db, member["id"], now - RATTRAPAGE_FENETRE
                )
                if open_session is None:
                    perimee = await get_recent_incomplete_session(db, member["id"])
                    if perimee is not None:
                        await interaction.response.send_message(
                            f"Ta session du {perimee['date']} (créneau {perimee['creneau']}) a été "
                            f"clôturée automatiquement et le délai de rattrapage (4h) est dépassé. "
                            f"Renseigne ton bilan toi-même avec `/session-corriger` "
                            f"(session #{perimee['id']}, champ `bilan`).",
                            ephemeral=True,
                        )
                    else:
                        await interaction.response.send_message(
                            "Tu n'as pas de session ouverte.", ephemeral=True
                        )
                    return
            else:
                channel = await _require_coworking_channel(interaction, db, wave["id"], "clôturer")
                if channel is None:
                    return

            # En rattrapage, `fin` a déjà été posée par l'auto-clôture RG-16 (fin réelle
            # de la session, pas l'instant où le membre exécute /session-end plus tard) —
            # on la préserve plutôt que d'écraser avec `now`, sinon la durée affichée
            # inclut à tort le délai entre l'auto-clôture et le rattrapage.
            fin = datetime.fromisoformat(open_session["fin"]) if rattrapage else now
            blocages_val = str(self.blocages) if self.blocages else None
            await end_session(db, open_session["id"], fin, str(self.bilan), blocages_val)

            debut = datetime.fromisoformat(open_session["debut"])
            duree = fin - debut
            duree_str = str(duree).split(".")[0]

            texte = f"{interaction.user.mention} clôture sa session — durée **{duree_str}**.\nBilan : {self.bilan}"
            if blocages_val:
                texte += f"\nBlocages : {blocages_val}"
            if rattrapage:
                texte += "\n-# Session rattrapée après une clôture automatique (créneau dépassé, RG-16)."
            await interaction.response.send_message(texte)


class SessionCorrigerModal(discord.ui.Modal):
    def __init__(self, id_session: int, champ: str, valeur_actuelle: str | None):
        super().__init__(title=f"Corriger la session #{id_session}")
        self.id_session = id_session
        self.champ = champ
        style = discord.TextStyle.short if champ == "creneau" else discord.TextStyle.paragraph
        self.valeur = discord.ui.TextInput(
            label=champ.capitalize(),
            style=style,
            max_length=1000,
            required=True,
            default=valeur_actuelle or "",
        )
        self.add_item(self.valeur)

    async def on_submit(self, interaction: discord.Interaction):
        valeur = str(self.valeur)

        if self.champ == "creneau" and valeur not in CRENEAUX:
            await interaction.response.send_message(
                f"Créneau invalide. Valeurs possibles : {', '.join(CRENEAUX)}", ephemeral=True
            )
            return

        async with get_connection() as db:
            await update_field(db, self.id_session, self.champ, valeur)

        await interaction.response.send_message(
            f"Session {self.id_session} mise à jour — `{self.champ}` → {valeur}", ephemeral=True
        )


class SessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="session-start", description="Démarre une session de coworking")
    async def session_start(self, interaction: discord.Interaction, creneau: str):
        await interaction.response.send_modal(SessionStartModal(creneau))

    @session_start.autocomplete("creneau")
    async def session_start_creneau_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Suggestions seulement — le champ reste libre (pas app_commands.choices), donc
        # taper un créneau hors liste (ex. "17h-19h") reste possible.
        async with get_connection() as db:
            db_creneaux = await list_distinct_creneaux(db)
        options = _sort_creneaux(set(CRENEAUX) | set(db_creneaux))
        if current:
            options = [c for c in options if current.lower() in c.lower()]
        return [app_commands.Choice(name=c, value=c) for c in options[:25]]

    @app_commands.command(name="session-end", description="Clôture ta session en cours")
    async def session_end(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SessionEndModal())

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

            valeur_actuelle = session[champ.value]

        await interaction.response.send_modal(
            SessionCorrigerModal(id_session, champ.value, valeur_actuelle)
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
