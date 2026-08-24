import logging

import discord
from discord.ext import commands

from bot.config import GUILD_ID, TOKEN
from bot.db.database import init_db
from bot.tasks.auto_close import auto_close_sessions

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("skillup")

INITIAL_COGS = (
    "bot.cogs.session",
    "bot.cogs.journal",
    "bot.cogs.admin",
    "bot.cogs.coworking_setup",
    "bot.cogs.guide",
)

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
# Nécessaire pour lire le contenu (content/embeds) des messages d'AUTRES membres via
# l'API REST (ex. synchro objectif de vague depuis un post existant, api/discord_client.py)
# — sans ce flag ET son équivalent activé dans Developer Portal, Discord renvoie ces champs
# vides (chaîne "") pour tout message qui n'est ni écrit par le bot, ni un DM, ni un message
# où le bot est mentionné, même si le fetch REST répond 200.
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("Connecté en tant que %s", bot.user)
    guild = discord.Object(id=GUILD_ID) if GUILD_ID else None
    if guild:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
    else:
        synced = await bot.tree.sync()
    log.info("Slash-commands synchronisées : %d", len(synced))
    if not auto_close_sessions.is_running():
        auto_close_sessions.start()


async def main():
    await init_db()
    for cog in INITIAL_COGS:
        await bot.load_extension(cog)
    await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
