from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

GUIDE_PATH = Path(__file__).parent.parent.parent / "GUIDE_UTILISATION.md"
MAX_CHUNK = 1900


def _chunk_markdown(text: str, max_len: int = MAX_CHUNK) -> list[str]:
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > max_len:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


class GuideCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="guide", description="Poste le guide d'utilisation du bot SkillUp dans ce salon"
    )
    async def guide(self, interaction: discord.Interaction):
        if not GUIDE_PATH.exists():
            await interaction.response.send_message(
                "Guide introuvable sur le serveur du bot.", ephemeral=True
            )
            return

        texte = GUIDE_PATH.read_text(encoding="utf-8")
        chunks = _chunk_markdown(texte)

        await interaction.response.send_message(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)


async def setup(bot: commands.Bot):
    await bot.add_cog(GuideCog(bot))
