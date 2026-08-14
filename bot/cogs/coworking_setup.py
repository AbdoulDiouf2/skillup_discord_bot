import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.admin import is_admin
from bot.db.coworking_channels import add_channel, list_channels, remove_channel
from bot.db.database import get_connection
from bot.db.waves import get_active_wave, list_waves


class _ChannelMultiSelect(discord.ui.Select):
    def __init__(self, options: list[tuple[str, str]], action: str, wave_id: int, wave_nom: str):
        super().__init__(
            placeholder="Choisis un ou plusieurs salons...",
            min_values=1,
            max_values=len(options),
            options=[
                discord.SelectOption(label=nom[:100], value=canal_id) for canal_id, nom in options
            ],
        )
        self.action = action
        self.wave_id = wave_id
        self.wave_nom = wave_nom

    async def callback(self, interaction: discord.Interaction):
        # Ne fait qu'enregistrer la sélection — l'écriture en base se fait au clic sur "Valider".
        noms = [next((o.label for o in self.options if o.value == v), v) for v in self.values]
        await interaction.response.edit_message(
            content=f"Sélection : {', '.join(noms)}\nClique sur **Valider** pour confirmer.",
            view=self.view,
        )


class _ValiderButton(discord.ui.Button):
    def __init__(self, select: _ChannelMultiSelect):
        super().__init__(label="Valider", style=discord.ButtonStyle.success, row=1)
        self.select = select

    async def callback(self, interaction: discord.Interaction):
        if not self.select.values:
            await interaction.response.send_message(
                "Sélectionne au moins un salon avant de valider.", ephemeral=True
            )
            return

        noms = []
        async with get_connection() as db:
            for canal_id in self.select.values:
                label = next((o.label for o in self.select.options if o.value == canal_id), canal_id)
                if self.select.action == "ajouter":
                    await add_channel(db, canal_id, label, self.select.wave_id)
                else:
                    await remove_channel(db, canal_id, self.select.wave_id)
                noms.append(label)

        verbe = "ajouté(s)" if self.select.action == "ajouter" else "retiré(s)"
        await interaction.response.edit_message(
            content=f"Salon(s) {verbe} pour la vague **{self.select.wave_nom}** : {', '.join(noms)}",
            view=None,
        )


class _ChannelMultiSelectView(discord.ui.View):
    def __init__(self, options: list[tuple[str, str]], action: str, wave_id: int, wave_nom: str):
        super().__init__(timeout=120)
        select = _ChannelMultiSelect(options, action, wave_id, wave_nom)
        self.add_item(select)
        self.add_item(_ValiderButton(select))


class CoworkingSetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="salon-coworking-ajouter",
        description="[Admin] Déclare un ou plusieurs salons vocaux comme salons de coworking",
    )
    @is_admin()
    async def salon_coworking_ajouter(self, interaction: discord.Interaction):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return
            deja_lies = await list_channels(db, wave["id"], actif_seulement=True)

        deja_ids = {c["canal_id"] for c in deja_lies}
        candidats = [c for c in interaction.guild.voice_channels if str(c.id) not in deja_ids]
        if not candidats:
            await interaction.response.send_message(
                "Tous les salons vocaux du serveur sont déjà ajoutés à cette vague.", ephemeral=True
            )
            return

        options = [(str(c.id), c.name) for c in candidats[:25]]
        await interaction.response.send_message(
            f"Choisis le(s) salon(s) à ajouter pour la vague **{wave['nom']}** :",
            view=_ChannelMultiSelectView(options, "ajouter", wave["id"], wave["nom"]),
            ephemeral=True,
        )

    @app_commands.command(
        name="salon-coworking-retirer",
        description="[Admin] Retire un ou plusieurs salons vocaux de la liste coworking",
    )
    @is_admin()
    async def salon_coworking_retirer(self, interaction: discord.Interaction):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return
            deja_lies = await list_channels(db, wave["id"], actif_seulement=True)

        if not deja_lies:
            await interaction.response.send_message(
                f"Aucun salon de coworking enregistré pour la vague **{wave['nom']}**.", ephemeral=True
            )
            return

        options = [(c["canal_id"], c["canal_nom"]) for c in deja_lies[:25]]
        await interaction.response.send_message(
            f"Choisis le(s) salon(s) à retirer pour la vague **{wave['nom']}** :",
            view=_ChannelMultiSelectView(options, "retirer", wave["id"], wave["nom"]),
            ephemeral=True,
        )

    @app_commands.command(
        name="salons-coworking-lister",
        description="[Admin] Liste les salons de coworking, par vague",
    )
    @is_admin()
    async def salons_coworking_lister(self, interaction: discord.Interaction, vague: int | None = None):
        async with get_connection() as db:
            channels = await list_channels(db, vague)

        if not channels:
            await interaction.response.send_message(
                "Aucun salon de coworking enregistré.", ephemeral=True
            )
            return

        lignes = [
            f"**{c['wave_nom']}** — {c['canal_nom']} (`{c['canal_id']}`) — "
            f"{'actif' if c['actif'] else 'inactif'}"
            for c in channels
        ]
        texte = "\n".join(lignes)
        await interaction.response.send_message(texte[:2000], ephemeral=True)

    @salons_coworking_lister.autocomplete("vague")
    async def salons_coworking_lister_vague_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
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
    await bot.add_cog(CoworkingSetupCog(bot))
