from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import ADMIN_ROLE_NAME

GUIDE_PATH = Path(__file__).parent.parent.parent / "GUIDE_UTILISATION.md"
MAX_EMBED_DESCRIPTION = 4096

AIDE_TEXTE_ADMIN = """
**Commandes admin**
• `/vague-creer`, `/vague-activer`, `/vague-cloturer`, `/vague-lister` — cycle de vie des vagues
• `/membre-ajouter`, `/membre-editer`, `/membres-lister` — gestion des membres
• `/binome-definir`, `/binome-retirer`, `/binomes-semaine` — gestion des binômes
• `/salon-coworking-ajouter`, `/salon-coworking-retirer` — salons reconnus comme coworking
• `/sessions-lister` — voir les sessions avec filtres (membre, vague, semaine, statut)
• `/session-corriger` — corrige/supprime aussi les sessions des autres membres"""

AIDE_TEXTE = """**Bot SkillUp — aide rapide**

Ce bot garde une trace de tes sessions de travail (coworking) pour que tu n'aies plus à scroller les salons pour retrouver ce que tu as fait.

**Pendant une session**
• `/session-start` — démarre une session (dans un salon vocal Coworking), avec ton objectif du jour
• `/session-end` — clôture, avec ton bilan (ce que t'as fait + blocages éventuels)

**Pour consulter**
• `/mon-journal` — tes sessions de la semaine
• `/binome-journal` — le journal de ton binôme (pour préparer son bilan)
• `/bilan-semaine` — un récap prêt à copier dans le forum objectifs

**Autres**
• `/objectif-vague` — définit ton objectif pour toute la vague
• `/session-corriger` — corrige une session mal saisie
• `/guide` — poste le guide complet dans ce salon (plus détaillé)

Un souci ou une commande qui refuse ? Le message d'erreur explique généralement quoi faire. Sinon, demande à un admin."""


def _format_for_discord(text: str) -> list[str]:
    """Convertit le markdown du guide en messages Discord lisibles :
    titres `#`/`##`/`###` en gras (Discord les rend en gros titres moches sinon),
    et découpage par section plutôt que par nombre de caractères brut."""
    sections: list[str] = []
    current_lines: list[str] = []

    def flush():
        if current_lines:
            sections.append("\n".join(current_lines).strip())
            current_lines.clear()

    for line in text.splitlines():
        if line.strip() == "---":
            continue
        if line.startswith("## "):
            flush()
            current_lines.append(f"**{line[3:].strip()}**")
        elif line.startswith("### "):
            current_lines.append(f"**{line[4:].strip()}**")
        elif line.startswith("# "):
            flush()
            current_lines.append(f"**{line[2:].strip()}**")
        else:
            current_lines.append(line)
    flush()

    chunks: list[str] = []
    current = ""
    for section in sections:
        if current and len(current) + len(section) + 2 > MAX_EMBED_DESCRIPTION:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{section}" if current else section
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
        chunks = _format_for_discord(texte)

        embeds = [
            discord.Embed(description=chunk, color=discord.Color.blurple())
            for chunk in chunks[:10]  # Discord limite à 10 embeds par message
        ]
        await interaction.response.send_message(embeds=embeds)

    @app_commands.command(
        name="aide", description="Résumé rapide des commandes du bot, en langage clair"
    )
    async def aide(self, interaction: discord.Interaction):
        texte = AIDE_TEXTE
        is_admin = any(r.name == ADMIN_ROLE_NAME for r in interaction.user.roles)
        if is_admin:
            texte += "\n" + AIDE_TEXTE_ADMIN
        await interaction.response.send_message(texte, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GuideCog(bot))
