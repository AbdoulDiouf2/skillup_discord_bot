import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.admin import is_admin
from bot.db.coworking_channels import add_channel, remove_channel
from bot.db.database import get_connection


class CoworkingSetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="salon-coworking-ajouter", description="[Admin] Déclare un salon vocal comme salon de coworking"
    )
    @is_admin()
    async def salon_coworking_ajouter(
        self, interaction: discord.Interaction, salon: discord.VoiceChannel
    ):
        async with get_connection() as db:
            await add_channel(db, str(salon.id), salon.name)

        await interaction.response.send_message(
            f"**{salon.name}** ajouté comme salon de coworking.", ephemeral=True
        )

    @app_commands.command(
        name="salon-coworking-retirer", description="[Admin] Retire un salon vocal de la liste coworking"
    )
    @is_admin()
    async def salon_coworking_retirer(
        self, interaction: discord.Interaction, salon: discord.VoiceChannel
    ):
        async with get_connection() as db:
            await remove_channel(db, str(salon.id))

        await interaction.response.send_message(
            f"**{salon.name}** retiré des salons de coworking.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CoworkingSetupCog(bot))
