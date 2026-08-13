# Procédure de déploiement — Bot SkillUp

Cible : VPS Linux (Ubuntu 22.04/24.04), ~4-6€/mois (OVH, Hetzner, Contabo...).
Pourquoi un VPS : disponibilité 24/7 garantie (contrairement aux offres PaaS gratuites qui se mettent en veille — point d'attention identifié au §11 du CDC), et une base SQLite se sauvegarde en copiant un simple fichier.

## 1. Provisionner le VPS

1. Créer une instance Ubuntu 22.04 ou 24.04 LTS chez le fournisseur choisi (le moins cher suffit : 1 vCPU / 1 Go RAM).
2. Se connecter en SSH :
   ```bash
   ssh root@<ip_du_serveur>
   ```
3. Créer un utilisateur dédié (éviter de tourner en root) :
   ```bash
   adduser skillup
   usermod -aG sudo skillup
   su - skillup
   ```

## 2. Installer les dépendances système

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv git
```

## 3. Récupérer le code

```bash
cd ~
git clone https://github.com/AbdoulDiouf2/skillup_discord_bot.git
cd skillup_discord_bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Configurer le `.env`

Le `.env` n'est **jamais** dans le dépôt git (voir `.gitignore`) — il se crée manuellement sur le serveur, une seule fois.

```bash
cp .env.example .env
nano .env
```

Renseigner :
```
DISCORD_TOKEN=<token du bot, depuis le Developer Portal Discord>
GUILD_ID=<id du serveur Alumni CPS>
DB_PATH=data/skillup.db
```

Le token est un secret : ne jamais le committer, ne jamais le partager en clair (leçon apprise pendant le dev — voir historique de session, le token affiché en console locale devait rester local).

## 5. Tourner en continu avec systemd

Créer le service :
```bash
sudo nano /etc/systemd/system/skillup-bot.service
```

Contenu :
```ini
[Unit]
Description=Bot Discord SkillUp
After=network.target

[Service]
Type=simple
User=skillup
WorkingDirectory=/home/skillup/skillup_discord_bot
Environment=PYTHONPATH=/home/skillup/skillup_discord_bot
ExecStart=/home/skillup/skillup_discord_bot/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activer et démarrer :
```bash
sudo systemctl daemon-reload
sudo systemctl enable skillup-bot
sudo systemctl start skillup-bot
```

Vérifier :
```bash
sudo systemctl status skillup-bot
journalctl -u skillup-bot -f      # logs en direct
```

`Restart=on-failure` : le bot redémarre seul en cas de crash. `enable` : redémarre aussi après un reboot du serveur.

## 6. Sauvegarde de la base SQLite

La base (`data/skillup.db`) est un fichier unique — sauvegarde simple par copie, mais **jamais à chaud sans précaution** (SQLite peut être en écriture). Utiliser la commande `.backup` intégrée à SQLite, qui gère la cohérence même bot actif.

Script de sauvegarde `~/skillup_discord_bot/backup.sh` :
```bash
#!/bin/bash
set -e
DATE=$(date +%Y-%m-%d_%H%M)
BACKUP_DIR=/home/skillup/backups
mkdir -p "$BACKUP_DIR"
sqlite3 /home/skillup/skillup_discord_bot/data/skillup.db ".backup '$BACKUP_DIR/skillup_$DATE.db'"
find "$BACKUP_DIR" -name "skillup_*.db" -mtime +30 -delete
```

```bash
chmod +x ~/skillup_discord_bot/backup.sh
```

Cron quotidien (3h du matin) :
```bash
crontab -e
```
Ajouter :
```
0 3 * * * /home/skillup/skillup_discord_bot/backup.sh
```

Recommandé en plus : rapatrier périodiquement les sauvegardes hors du VPS (ex. `rsync` vers une machine perso, ou upload vers un stockage cloud) — une sauvegarde qui reste sur la même machine que la base ne protège pas contre une panne du serveur.

## 7. Mettre à jour le bot (nouvelle version du code)

```bash
cd ~/skillup_discord_bot
sudo systemctl stop skillup-bot
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl start skillup-bot
```

## 8. Purge des données d'un membre (RGPD léger, §13 du CDC)

Sur demande d'un membre, supprimer ses données :
```bash
sqlite3 ~/skillup_discord_bot/data/skillup.db
DELETE FROM sessions WHERE member_id = <id>;
DELETE FROM members WHERE id = <id>;
```
(Vérifier d'abord l'id via `SELECT * FROM members WHERE discord_id = '<discord_id>';`)

## Checklist de mise en prod

- [ ] VPS provisionné, accès SSH fonctionnel
- [ ] `.env` renseigné avec le vrai token de prod (différent du bot de dev)
- [ ] Bot invité sur le serveur Alumni CPS avec le scope `bot` + `applications.commands` (voir leçon apprise en dev : un bot invité sans scope `bot` n'est jamais réellement membre du serveur)
- [ ] Intents `Server Members` activé sur le Developer Portal (nécessaire pour la détection vocale RG-11/RG-12)
- [ ] Rôle Discord `Admin SkillUp` créé et attribué à l'équipe qui pilote l'initiative
- [ ] Salons de coworking déclarés via `/salon-coworking-ajouter`
- [ ] Vague créée via `/vague-creer` (brouillon), **activée via `/vague-activer`**, membres ajoutés via `/membre-ajouter`
- [ ] Service systemd actif, `enable` pour survivre à un reboot
- [ ] Cron de sauvegarde en place et testé une fois manuellement
