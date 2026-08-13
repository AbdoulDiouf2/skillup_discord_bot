from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import ADMIN_ROLE_NAME, TZ
from bot.db.database import get_connection
from bot.db.binomes import BinomeError, define_binome, get_partner_id, list_binomes_semaine, remove_binome
from bot.db.members import add_member, get_member, get_member_by_id, list_by_wave
from bot.db.sessions import list_filtered
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


async def _safe_dm(member: discord.Member, content: str) -> bool:
    if member.bot:
        return False
    try:
        await member.send(content)
        return True
    except discord.HTTPException:
        return False


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

        ok = await _safe_dm(
            utilisateur,
            f"Tu as été ajouté à la vague **{wave['nom']}** ({profil.value}). Bienvenue !\n\n"
            f"Pense à poster ton objectif de vague dans le forum `objectifs`. "
            f"Tu peux aussi le renseigner via `/objectif-vague` (à taper **dans un salon du "
            f"serveur**, pas ici en message privé) — ça sert de contexte au bot pour "
            f"générer tes bilans, en complément du forum.\n\n"
            f"Pour démarrer ta première session : `/session-start`, également sur le serveur.",
        )

        message = f"{utilisateur.mention} ajouté à la vague **{wave['nom']}** ({profil.value})."
        if not ok:
            message += "\n⚠️ DM non délivré (DMs probablement fermés)."

        await interaction.response.send_message(message, ephemeral=True)

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

            try:
                await define_binome(db, wave["id"], semaine, ma["id"], mb["id"])
            except BinomeError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

        ok_a = await _safe_dm(
            membre_a,
            f"Tu es en binôme avec **{membre_b.display_name}** pour la semaine {semaine} "
            f"de la vague **{wave['nom']}**.",
        )
        ok_b = await _safe_dm(
            membre_b,
            f"Tu es en binôme avec **{membre_a.display_name}** pour la semaine {semaine} "
            f"de la vague **{wave['nom']}**.",
        )

        message = f"Binôme semaine {semaine} : {membre_a.mention} ↔ {membre_b.mention}"
        echecs = [m.mention for m, ok in ((membre_a, ok_a), (membre_b, ok_b)) if not ok]
        if echecs:
            message += f"\n⚠️ DM non délivré à : {', '.join(echecs)} (DMs probablement fermés)."

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name="binome-retirer", description="[Admin] Dissout un binôme pour une semaine"
    )
    @is_admin()
    async def binome_retirer(
        self,
        interaction: discord.Interaction,
        semaine: int,
        membre_a: discord.Member,
        membre_b: discord.Member | None = None,
    ):
        async with get_connection() as db:
            wave = await get_active_wave(db)
            if wave is None:
                await interaction.response.send_message("Aucune vague active.", ephemeral=True)
                return

            ma = await get_member(db, str(membre_a.id), wave["id"])
            if ma is None:
                await interaction.response.send_message(
                    f"{membre_a.mention} n'est pas membre de la vague active.", ephemeral=True
                )
                return

            partner_id = await get_partner_id(db, ma["id"], wave["id"], semaine)
            partner_member_row = await get_member_by_id(db, partner_id) if partner_id else None

            removed = await remove_binome(db, wave["id"], semaine, ma["id"])
            if not removed:
                await interaction.response.send_message(
                    f"{membre_a.mention} n'était dans aucun binôme pour la semaine {semaine}.",
                    ephemeral=True,
                )
                return

        echecs = []
        ok_a = await _safe_dm(
            membre_a, f"Ton binôme de la semaine {semaine} (vague **{wave['nom']}**) a été dissous."
        )
        if not ok_a:
            echecs.append(membre_a.mention)

        partner_discord = None
        if partner_member_row is not None:
            partner_discord = interaction.guild.get_member(int(partner_member_row["discord_id"]))
            if partner_discord is None:
                try:
                    partner_discord = await interaction.guild.fetch_member(
                        int(partner_member_row["discord_id"])
                    )
                except discord.NotFound:
                    partner_discord = None
            if partner_discord is not None:
                ok_b = await _safe_dm(
                    partner_discord,
                    f"Ton binôme de la semaine {semaine} (vague **{wave['nom']}**) a été dissous.",
                )
                if not ok_b:
                    echecs.append(partner_discord.mention)

        message = f"Binôme de {membre_a.mention} dissous pour la semaine {semaine}."
        if echecs:
            message += f"\n⚠️ DM non délivré à : {', '.join(echecs)} (DMs probablement fermés)."

        await interaction.response.send_message(message, ephemeral=True)

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
        name="membres-lister", description="[Admin] Liste les membres d'une vague (défaut : vague active)"
    )
    @is_admin()
    async def membres_lister(self, interaction: discord.Interaction, vague: int | None = None):
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

            membres = await list_by_wave(db, wave["id"])

        if not membres:
            await interaction.response.send_message(
                f"Aucun membre enregistré dans la vague **{wave['nom']}**.", ephemeral=True
            )
            return

        lignes = [
            f"<@{m['discord_id']}> — {m['profil']}"
            + (f" · {m['certif_ou_projet']}" if m["certif_ou_projet"] else "")
            for m in membres
        ]
        await interaction.response.send_message(
            f"**Membres — {wave['nom']}** ({len(membres)})\n\n" + "\n".join(lignes),
            ephemeral=True,
        )

    @membres_lister.autocomplete("vague")
    async def membres_lister_vague_autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_connection() as db:
            waves = await list_waves(db)
        choices = []
        for w in waves:
            label = f"#{w['id']} · {w['nom']} ({w['statut']})"
            if current and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label[:100], value=w["id"]))
        return choices[:25]

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

    @app_commands.command(
        name="sessions-lister", description="[Admin] Liste les sessions avec filtres optionnels"
    )
    @app_commands.choices(
        statut=[
            app_commands.Choice(name=s, value=s) for s in ("ouverte", "complète", "incomplète")
        ]
    )
    @is_admin()
    async def sessions_lister(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
        vague: int | None = None,
        semaine: int | None = None,
        statut: app_commands.Choice[str] | None = None,
    ):
        async with get_connection() as db:
            member_id = None
            if membre is not None:
                if vague is not None:
                    wave_for_member = await get_wave_by_id(db, vague)
                else:
                    wave_for_member = await get_active_wave(db)
                if wave_for_member is None:
                    await interaction.response.send_message(
                        "Vague introuvable ou aucune vague active.", ephemeral=True
                    )
                    return
                m = await get_member(db, str(membre.id), wave_for_member["id"])
                if m is None:
                    await interaction.response.send_message(
                        f"{membre.mention} n'est pas membre de cette vague.", ephemeral=True
                    )
                    return
                member_id = m["id"]

            sessions = await list_filtered(
                db,
                wave_id=vague,
                semaine=semaine,
                member_id=member_id,
                statut=statut.value if statut else None,
            )

        if not sessions:
            await interaction.response.send_message(
                "Aucune session ne correspond à ces critères.", ephemeral=True
            )
            return

        lignes = []
        for s in sessions:
            duree = ""
            if s["fin"]:
                debut = datetime.fromisoformat(s["debut"])
                fin = datetime.fromisoformat(s["fin"])
                duree = f" ({str(fin - debut).split('.')[0]})"
            lignes.append(
                f"#{s['id']} · {s['date']} · {s['creneau']} · {s['membre_nom']} · "
                f"{s['wave_nom']} S{s['semaine']} · {s['statut']}{duree}"
            )

        texte = f"**Sessions** ({len(sessions)})\n\n" + "\n".join(lignes)
        if len(texte) > 1900:
            texte = texte[:1900] + "\n… (tronqué, affine les filtres)"

        await interaction.response.send_message(texte, ephemeral=True)

    @sessions_lister.autocomplete("vague")
    async def sessions_lister_vague_autocomplete(self, interaction: discord.Interaction, current: str):
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
