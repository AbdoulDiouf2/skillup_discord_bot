from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import ADMIN_ROLE_NAME, TZ
from bot.db.database import get_connection
from bot.db.binomes import define_binome, list_binomes_semaine
from bot.db.members import add_member, get_member
from bot.db.waves import (
    WaveError,
    activate_wave,
    close_wave,
    create_wave,
    get_active_wave,
    get_wave_by_id,
    list_waves,
)
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
            f"Vague **{nom}** créée en brouillon (id {wave_id}, du {debut} au {fin}). "
            f"Utilise `/vague-activer` pour l'activer.",
            ephemeral=True,
        )

    @app_commands.command(name="vague-activer", description="[Admin] Active une vague en brouillon")
    @is_admin()
    async def vague_activer(self, interaction: discord.Interaction, vague_id: int):
        async with get_connection() as db:
            try:
                wave = await activate_wave(db, vague_id)
            except WaveError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

        await interaction.response.send_message(
            f"Vague **{wave['nom']}** activée.", ephemeral=True
        )

    @vague_activer.autocomplete("vague_id")
    async def vague_activer_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        async with get_connection() as db:
            waves = await list_waves(db, statut="brouillon")
        choices = []
        for w in waves:
            label = f"#{w['id']} · {w['nom']} · {w['date_debut']} → {w['date_fin']}"
            if current and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=w["id"]))
        return choices[:25]

    @app_commands.command(
        name="vague-cloturer", description="[Admin] Clôture une vague (par défaut la vague active)"
    )
    @is_admin()
    async def vague_cloturer(self, interaction: discord.Interaction, vague_id: int | None = None):
        async with get_connection() as db:
            try:
                wave = await close_wave(db, vague_id)
            except WaveError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

        await interaction.response.send_message(
            f"Vague **{wave['nom']}** clôturée.", ephemeral=True
        )

    @vague_cloturer.autocomplete("vague_id")
    async def vague_cloturer_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        async with get_connection() as db:
            waves = await list_waves(db, statut="active")
        choices = []
        for w in waves:
            label = f"#{w['id']} · {w['nom']} · {w['date_debut']} → {w['date_fin']}"
            if current and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=w["id"]))
        return choices[:25]

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

    @app_commands.command(name="vague-lister", description="[Admin] Liste toutes les vagues et leur statut")
    @is_admin()
    async def vague_lister(self, interaction: discord.Interaction):
        async with get_connection() as db:
            waves = await list_waves(db)

        if not waves:
            await interaction.response.send_message("Aucune vague enregistrée.", ephemeral=True)
            return

        lignes = [
            f"#{w['id']} · **{w['nom']}** — {w['statut']} ({w['date_debut']} → {w['date_fin']})"
            for w in waves
        ]
        await interaction.response.send_message(
            "**Vagues**\n\n" + "\n".join(lignes), ephemeral=True
        )

    @app_commands.command(
        name="binomes-semaine", description="[Admin] Liste les binômes constitués pour une semaine"
    )
    @is_admin()
    async def binomes_semaine(
        self,
        interaction: discord.Interaction,
        semaine: int | None = None,
        vague: int | None = None,
    ):
        async with get_connection() as db:
            if vague is not None:
                wave = await get_wave_by_id(db, vague)
                if wave is None:
                    await interaction.response.send_message("Vague introuvable.", ephemeral=True)
                    return
            else:
                wave = await get_active_wave(db)
                if wave is None:
                    await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                    return

            if semaine is not None:
                target_semaine = semaine
            else:
                wave_start = datetime.fromisoformat(wave["date_debut"]).date()
                target_semaine = week_number_for_date(datetime.now(TZ).date(), wave_start)

            binomes = await list_binomes_semaine(db, wave["id"], target_semaine)

        if not binomes:
            await interaction.response.send_message(
                f"Aucun binôme constitué pour la vague **{wave['nom']}**, semaine {target_semaine}.",
                ephemeral=True,
            )
            return

        lignes = [f"{b['nom_a']} ↔ {b['nom_b']}" for b in binomes]
        await interaction.response.send_message(
            f"**Binômes — {wave['nom']}, semaine {target_semaine}**\n\n" + "\n".join(lignes),
            ephemeral=True,
        )

    @binomes_semaine.autocomplete("vague")
    async def binomes_semaine_vague_autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_connection() as db:
            waves = await list_waves(db)
        choices = []
        for w in waves:
            label = f"#{w['id']} · {w['nom']} ({w['statut']})"
            if current and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=w["id"]))
        return choices[:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
