# Bot SkillUp

Bot Discord d'accompagnement des sessions SkillUp — Alumni CPS.

Voir [Cahier_des_Charges_Bot_Skill_Up.md](Cahier_des_Charges_Bot_Skill_Up.md) pour le détail fonctionnel.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate   # ou source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # puis remplir DISCORD_TOKEN et GUILD_ID
python -m bot.main
```

## Structure

```
bot/
  main.py          # point d'entrée, chargement des cogs
  config.py        # variables d'environnement, fuseau horaire
  cogs/             # slash-commands (session, journal, admin...)
  db/               # accès SQLite, schéma, requêtes
data/               # fichier skillup.db (ignoré par git)
tests/
```
