# Bot SkillUp

Bot Discord + API d'accompagnement des sessions SkillUp — Alumni CPS.

Voir [Cahier_des_Charges_Bot_Skill_Up.md](Cahier_des_Charges_Bot_Skill_Up.md) pour le détail fonctionnel
et [DEPLOIEMENT.md](DEPLOIEMENT.md) pour le déploiement (VPS Docker + Caddy, Neon Postgres, CI/CD).

## Setup

Base de données : Postgres (Neon en prod/dev, `DATABASE_URL` dans `.env`).

```bash
python -m venv .venv
.venv/Scripts/activate   # ou source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # puis remplir DISCORD_TOKEN, GUILD_ID, DATABASE_URL, API_KEY
python -m bot.main       # bot Discord
uvicorn api.main:app --reload   # API (utilisée par CPS Connect)
```

Ou via Docker (reproduit l'environnement de prod) :
```bash
docker compose up -d --build
```

## Structure

```
bot/
  main.py          # point d'entrée du bot, chargement des cogs
  config.py        # variables d'environnement, fuseau horaire
  cogs/             # slash-commands (session, journal, admin, coworking...)
  db/               # accès Postgres (asyncpg), schéma, requêtes
  services/         # logique métier partagée (bot + api)
api/
  main.py          # point d'entrée FastAPI
  discord_client.py # appels REST Discord (rôles, membres, salons)
  routers/          # endpoints (journal, vagues, admin)
tests/
```
