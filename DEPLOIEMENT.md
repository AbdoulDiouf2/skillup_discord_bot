# Procédure de déploiement — Bot & API SkillUp

Cible : VPS mutualisé `maadec-infra-01` (Hetzner, Docker + Caddy), accès admin
réservé au réseau Tailscale. Base de données : **Neon Postgres** (cloud, aucune
base hébergée sur le VPS).

Deux services déployés :
- **`skillup-bot`** — worker (bot Discord), aucune entrée HTTP.
- **`skillup-api`** — API FastAPI lecture/écriture, utilisée par CPS Connect,
  exposée en HTTPS via Caddy sur `https://skillup-api.maadec.com`.

## 1. Provisionner (déjà fait)

Le VPS `maadec-infra-01` est partagé entre plusieurs projets. Voir
`VPS_ENVIRONMENT_maadec-infra-01.md` pour les détails complets (réseaux Docker,
Caddy, règles à ne jamais violer). Accès SSH uniquement via Tailscale.

## 2. Premier déploiement manuel

```bash
ssh maadec@<ip-tailscale-du-vps>
mkdir -p ~/infra/prod
cd ~/infra/prod
git clone https://github.com/AbdoulDiouf2/skillup_discord_bot.git
cd skillup_discord_bot
```

### `.env` (jamais commité)

```bash
nano .env
```

```
DISCORD_TOKEN=<token bot PROD, Developer Portal>
GUILD_ID=<ID serveur Alumni CPS prod>
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require   # Neon, même base pour bot ET api
API_KEY=<clé partagée avec CPS Connect, header X-API-Key>
```

`DATABASE_URL` et `API_KEY` **doivent être identiques** entre le bot et l'API
(même `.env`, chargé par les deux services) — sinon incohérence de données ou
401 côté CPS Connect.

### Build & run

```bash
docker compose up -d --build
docker compose logs -f
```

## 3. Exposition HTTP de l'API (Caddy)

DNS chez Hostinger (hPanel) : enregistrement **A** `skillup-api` → IP publique
du VPS, sans proxy.

```bash
nano ~/infra/caddy/Caddyfile
```
```
skillup-api.maadec.com {
    reverse_proxy skillup-api:8000
}
```
```bash
cd ~/infra/caddy && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Vérifier : `curl https://skillup-api.maadec.com/health` → `{"status":"ok"}`.

## 4. Invitation du bot sur le serveur Discord prod

Lien OAuth2 (scope `bot` + `applications.commands`, permissions : Send
Messages, Read Message History, Manage Threads, Embed Links, View Channels,
Use Slash Commands) :
```
https://discord.com/oauth2/authorize?client_id=<CLIENT_ID_PROD>&permissions=19327437824&scope=bot%20applications.commands
```

Un bot invité sans le scope `bot` n'est jamais réellement membre du serveur —
`bot.tree.sync(guild=...)` échoue alors en `403 Forbidden`. S'il n'est pas
invité du tout, l'API échoue en `404 Unknown Guild` sur les appels
`/guilds/{GUILD_ID}/...`.

Checklist Developer Portal / serveur :
- [ ] Scope `bot` + `applications.commands`
- [ ] Intent **Server Members** activé (nécessaire RG-11/RG-12, détection vocale)
- [ ] Rôle Discord `Admin SkillUp` créé
- [ ] Permission **`Manage Server`** cochée sur le rôle `Admin SkillUp` — permet
      aux commandes admin (`default_permissions(manage_guild=True)` côté code)
      de s'afficher par défaut, sans toggle manuel par commande dans
      Paramètres serveur → Intégrations

## 5. Firebase (CPS Connect) — secrets Cloud Functions

`functions/index.js` (repo CPS Connect) relaie les appels vers l'API SkillUp
via `skillupProxy` — le frontend n'appelle jamais l'API directement.

```bash
firebase functions:secrets:set SKILLUP_API_URL       # https://skillup-api.maadec.com
firebase functions:secrets:set SKILLUP_API_KEY        # = API_KEY du .env VPS
firebase functions:secrets:set DISCORD_CLIENT_ID      # app OAuth prod, Developer Portal
firebase functions:secrets:set DISCORD_CLIENT_SECRET
firebase functions:secrets:set DISCORD_REDIRECT_URI   # doit matcher OAuth2 → Redirects sur l'app
```
Chaque `secrets:set` propose un redeploy automatique des fonctions concernées.

`DISCORD_REDIRECT_URI` doit être enregistrée à l'identique (casse, trailing
slash) dans Developer Portal → OAuth2 → Redirects de l'app prod, sinon
`invalid_redirect_uri`.

Dev/test séparé de prod : la Cloud Function déployée reste toujours branchée
sur prod. Pour tester en local sans y toucher, utiliser l'émulateur Firebase
avec `functions/.secret.local` (gitignored) pointant vers l'API dev (Vercel).

## 6. CI/CD — déploiement automatique

Workflow `.github/workflows/deploy.yml` : chaque push sur `main` rejoint le
tailnet (clé Tailscale éphémère) puis SSH sur le VPS pour `git pull` +
`docker compose up -d --build`.

Secrets GitHub requis (repo → Settings → Secrets and variables → Actions) :

| Secret | Contenu |
|---|---|
| `TS_AUTHKEY` | clé Tailscale (admin console → Settings → Keys → Generate auth key, reusable + ephemeral) |
| `DEPLOY_SSH_KEY` | clé privée SSH dédiée, dont la publique est dans `~/.ssh/authorized_keys` sur le VPS |
| `VPS_HOST` | IP Tailscale du VPS (`tailscale ip -4` sur le VPS) |

Déploiement manuel toujours possible en cas de besoin (section 2, `docker
compose up -d --build`).

## 7. Mettre à jour manuellement (hors CI/CD)

```bash
cd ~/infra/prod/skillup_discord_bot
git pull origin main
docker compose up -d --build
```

## 8. Sauvegarde de la base

Neon gère ses propres snapshots/point-in-time recovery côté cloud — pas de
script de backup local nécessaire (contrairement à l'ancienne cible SQLite).
Vérifier la politique de rétention dans la console Neon si besoin de la
renforcer.

## 9. Purge des données d'un membre (RGPD léger, §13 du CDC)

Sur demande d'un membre, se connecter à la base Neon (`psql "$DATABASE_URL"`
ou console Neon) :
```sql
SELECT * FROM members WHERE discord_id = '<discord_id>';   -- récupérer l'id d'abord
DELETE FROM sessions WHERE member_id = <id>;
DELETE FROM members WHERE id = <id>;
```

## Checklist de mise en prod

- [x] VPS provisionné, Docker + Caddy en place (`maadec-infra-01`)
- [x] `.env` renseigné avec le vrai token de prod (différent du bot de dev)
- [x] Bot invité sur le serveur Alumni CPS avec le scope `bot` + `applications.commands`
- [x] Intent `Server Members` activé
- [x] Rôle Discord `Admin SkillUp` créé, permission `Manage Server` cochée
- [ ] Salons de coworking déclarés via `/salon-coworking-ajouter`
- [ ] Vague créée via `/vague-creer` (brouillon), activée via `/vague-activer`, membres ajoutés via `/membre-ajouter`
- [x] `skillup-api` exposée en HTTPS (`skillup-api.maadec.com`), `/health` OK
- [x] Secrets Firebase (`SKILLUP_API_URL`, `SKILLUP_API_KEY`, `DISCORD_CLIENT_*`) à jour côté CPS Connect
- [x] CI/CD GitHub Actions en place (déploiement auto sur push `main`)
- [ ] `/guide` posté et épinglé dans un salon de référence
- [ ] Commandes admin masquées aux non-admins via toggle Discord (optionnel — `default_permissions` gère déjà le cas par défaut)
