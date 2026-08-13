from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import ADMIN_ROLE_NAME, TZ
from bot.db.database import get_connection
from bot.db.binomes import define_binome
from bot.db.members import add_member, get_member
from bot.db.waves import create_wave, get_active_wave
from bot.services.weeks import week_number_for_date

PROFILS = ("étudiant", "demandeur d'emploi", "cadre", "alternant", "autre")


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not any(r.name == ADMIN_ROLE_NAME for r in interaction.user.roles):
            await interaction.response.send_message(
                "Réservé aux admins SkillUp.", ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vague-creer", description="[Admin] Crée une nouvelle vague")
    @is_admin()
    async def vague_creer(
        self, interaction: discord.Interaction, nom: str, date_debut: str, date_fin: str
    ):
        try:
            debut = datetime.strptime(date_debut, "%d/%m/%Y").date()
            fin = datetime.strptime(date_fin, "%d/%m/%Y").date()
        except ValueError:
            await interaction.response.send_message(
                "Format de date invalide. Utilise JJ/MM/AAAA.", ephemeral=True
            )
            return

        async with get_connection() as db:
            wave_id = await create_wave(db, nom, debut, fin)

        await interaction.response.send_message(
            f"Vague **{nom}** créée et activée (id {wave_id}, du {debut} au {fin}).",
            ephemeral=True,
        )

    @app_commands.command(name="membre-ajouter", description="[Admin] Ajoute un membre à la vague active")
    @app_commands.choices(
        profil=[app_commands.Choice(name=p, value=p) for p in PROFILS]
    )
    @is_admin()
    async def membre_ajouter(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        profil: app_commands.Choice[str],
        certif_ou_projet: str | None = None,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            existing = await get_member(db, str(utilisateur.id), wave["id"])
            if existing is not None:
                await interaction.response.send_message(
                    f"{utilisateur.mention} est déjà membre de la vague active.", ephemeral=True
                )
                return

            await add_member(
                db, str(utilisateur.id), utilisateur.display_name, profil.value, wave["id"], certif_ou_projet
            )

        await interaction.response.send_message(
            f"{utilisateur.mention} ajouté à la vague **{wave['nom']}** ({profil.value}).",
            ephemeral=True,
        )

    @app_commands.command(name="membre-editer", description="[Admin] Édite un champ d'un membre")
    @app_commands.choices(
        champ=[
            app_commands.Choice(name=c, value=c)
            for c in ("nom", "profil", "certif_ou_projet", "objectif_vague")
        ]
    )
    @is_admin()
    async def membre_editer(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        champ: app_commands.Choice[str],
        valeur: str,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            member = await get_member(db, str(utilisateur.id), wave["id"])
            if member is None:
                await interaction.response.send_message(
                    f"{utilisateur.mention} n'est pas membre de la vague active.", ephemeral=True
                )
                return

            await db.execute(
                f"UPDATE members SET {champ.value} = ? WHERE id = ?", (valeur, member["id"])
            )
            await db.commit()

        await interaction.response.send_message(
            f"{utilisateur.mention} : `{champ.value}` mis à jour → {valeur}", ephemeral=True
        )

    @app_commands.command(name="binome-definir", description="[Admin] Définit un binôme pour une semaine")
    @is_admin()
    async def binome_definir(
        self,
        interaction: discord.Interaction,
        semaine: int,
        membre_a: discord.Member,
        membre_b: discord.Member,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            ma = await get_member(db, str(membre_a.id), wave["id"])
            mb = await get_member(db, str(membre_b.id), wave["id"])
            if ma is None or mb is None:
                await interaction.response.send_message(
                    "Les deux membres doivent être enregistrés dans la vague active.",
                    ephemeral=True,
                )
                return

            await define_binome(db, wave["id"], semaine, ma["id"], mb["id"])

        await interaction.response.send_message(
            f"Binôme semaine {semaine} : {membre_a.mention} ↔ {membre_b.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
