"""Backfill des sessions d'août 2026 (reconstruction manuelle depuis Discord).

Exécution : python scripts/import_backfill.py [--dry-run] [--clean]
Fait, dans l'ordre, en une seule exécution :
  0. (si --clean) vide sessions/members/coworking_channels/waves — TOUTE la base,
     pas seulement la vague "Vague Août 2026". Nécessaire avant réimport car un
     run précédent peut avoir laissé des données partielles (vague déjà active,
     membres déjà ajoutés) qui font échouer create_wave/activate_wave.
  1. crée + active la vague "Vague Août 2026"
  2. réenregistre les 2 salons coworking
  3. ajoute les 8 membres
  4. importe les 57 sessions du JSON

--clean : DESTRUCTEUR, vide toute la base avant import. À utiliser seulement si
tu veux repartir de zéro (ex. run précédent en échec partiel). Sans ce flag, le
script échoue proprement si une vague est déjà active plutôt que de dupliquer.

--dry-run : ne touche pas la DB (aucune connexion ouverte). Valide MEMBERS,
parse le JSON, résout canaux/dates/semaines et affiche ce qui serait importé
vs ignoré. La DB ici valide chaque instruction immédiatement (asyncpg
autocommit, pas de vraie transaction) donc un rollback après coup n'est pas
fiable — le dry-run doit rester 100% simulé, jamais un vrai run annulé après coup.

N'importe rien via des commandes Discord — script autonome, direct sur la DB.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.db.database import get_connection, init_db
from bot.db.waves import activate_wave, create_wave
from bot.db.coworking_channels import add_channel
from bot.db.members import add_member

load_dotenv()

TZ = ZoneInfo("Europe/Paris")
JSON_PATH = Path(__file__).parent.parent / "public" / "backfill_sessions_skillup (1).json"

WAVE_NOM = "Vague Août 2026"
WAVE_DATE_DEBUT = date(2026, 8, 2)
WAVE_DATE_FIN = date(2026, 8, 30)

# Salons coworking déjà connus (mêmes IDs que ceux enregistrés précédemment via Discord).
CHANNELS = [
    ("1537459536036896899", "Coworking 1"),
    ("1537459775338717204", "Coworking 2"),
]

# Discord IDs + profils réels des membres : donnée personnelle, jamais en dur dans
# le script (repo public). Chargée depuis .env (BACKFILL_MEMBERS, JSON), non versionné.
_raw = os.environ.get("BACKFILL_MEMBERS")
if not _raw:
    print("ERREUR — variable d'environnement BACKFILL_MEMBERS absente (voir .env).")
    sys.exit(1)
MEMBERS: dict[str, dict] = json.loads(_raw)

# Résolution du nom de canal texte -> nom de canal enregistré. Le cas ambigu
# "Coworking 2 (objectif) / Coworking 1 (bilan)" (bf-014) est tranché sur le
# salon de DÉMARRAGE (Coworking 2), cohérent avec RG-11 (canal détecté au
# moment de /session-start, pas à la clôture).
CANAL_RESOLUTION = {
    "Coworking 1": "Coworking 1",
    "Coworking 2": "Coworking 2",
    "Coworking 2 (objectif) / Coworking 1 (bilan)": "Coworking 2",
}


def week_number_for_date(d: date, wave_start: date) -> int:
    from datetime import timedelta

    first_monday = wave_start + timedelta(days=(7 - wave_start.weekday()) % 7)
    if wave_start.weekday() == 0:
        first_monday = wave_start
    if d < first_monday:
        return 0
    return ((d - first_monday).days // 7) + 1


async def clean_db(db) -> None:
    """Vide toute la base (sessions, members, coworking_channels, waves) — ordre
    respectant les FK (sessions dépend de members/waves, members/channels de waves)."""
    counts = {}
    for table in ("sessions", "members", "coworking_channels", "waves"):
        r = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
        counts[table] = (await r.fetchone())["c"]

    print("Nettoyage complet de la base avant import :")
    for table, n in counts.items():
        print(f"  - {table} : {n} ligne(s) à supprimer")

    await db.execute("DELETE FROM sessions")
    await db.execute("DELETE FROM members")
    await db.execute("DELETE FROM coworking_channels")
    await db.execute("DELETE FROM waves")
    print("Base vidée.\n")


async def main(dry_run: bool, clean: bool):
    missing = [nom for nom, info in MEMBERS.items() if not info["discord_id"] or not info["profil"]]
    if missing:
        print("ERREUR — MEMBERS incomplet, remplis discord_id/profil pour :")
        for nom in missing:
            print(f"  - {nom}")
        print("\nAucune modification effectuée sur la base. Arrêt.")
        return

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    sessions_json = data["sessions"]

    erreurs: list[str] = []
    avertissements: list[str] = []
    stats = {"waves": 0, "coworking_channels": 0, "members": 0, "sessions": 0, "sessions_ignorees": 0}

    if dry_run:
        print("=" * 60)
        print("DRY-RUN — aucune connexion DB, aucune écriture. Simulation uniquement.")
        print("=" * 60)
        if clean:
            print("[dry-run] --clean : viderait sessions/members/coworking_channels/waves (pas de suppression réelle).")
        stats["waves"] = 1
        stats["coworking_channels"] = len(CHANNELS)
        stats["members"] = len(MEMBERS)
        member_id_by_nom = {nom: -1 for nom in MEMBERS}  # placeholder, pas de vrai id en dry-run
        print(f"[dry-run] créerait la vague : {WAVE_NOM} ({WAVE_DATE_DEBUT} -> {WAVE_DATE_FIN})")
        print(f"[dry-run] enregistrerait {stats['coworking_channels']} salon(s) coworking.")
        print(f"[dry-run] ajouterait {stats['members']} membre(s).")
    else:
        await init_db()

    db_ctx = get_connection() if not dry_run else None
    db = await db_ctx.__aenter__() if db_ctx else None

    try:
        if not dry_run and clean:
            await clean_db(db)

        if not dry_run:
            # 1. Vague
            wave_id = await create_wave(db, WAVE_NOM, WAVE_DATE_DEBUT, WAVE_DATE_FIN)
            await activate_wave(db, wave_id)
            stats["waves"] += 1
            print(f"Vague créée et activée : {WAVE_NOM} (id {wave_id})")

            # 2. Salons coworking
            for canal_id, canal_nom in CHANNELS:
                await add_channel(db, canal_id, canal_nom, wave_id)
                stats["coworking_channels"] += 1
            print(f"{stats['coworking_channels']} salon(s) coworking enregistré(s).")

            # 3. Membres
            member_id_by_nom: dict[str, int] = {}
            for nom, info in MEMBERS.items():
                member_id = await add_member(
                    db, info["discord_id"], nom, info["profil"], wave_id, info["certif_ou_projet"]
                )
                member_id_by_nom[nom] = member_id
                stats["members"] += 1
            print(f"{stats['members']} membre(s) ajouté(s).")

        # 4. Sessions
        for entry in sessions_json:
            sid = entry["id"]

            nom = entry["membre"]
            member_id = member_id_by_nom.get(nom)
            if member_id is None:
                erreurs.append(f"{sid} : membre '{nom}' introuvable — ignorée.")
                stats["sessions_ignorees"] += 1
                continue

            canal_brut = entry["canal"]
            canal_nom = CANAL_RESOLUTION.get(canal_brut)
            if canal_nom is None:
                erreurs.append(f"{sid} : canal '{canal_brut}' non résolu — ignorée.")
                stats["sessions_ignorees"] += 1
                continue
            canal_id = next((cid for cid, cnom in CHANNELS if cnom == canal_nom), None)

            creneau = entry["creneau"]

            y, m, d = map(int, entry["date"].split("-"))
            session_date = date(y, m, d)

            semaine_json = entry["semaine"]
            semaine_calc = week_number_for_date(session_date, WAVE_DATE_DEBUT)
            if semaine_calc != semaine_json:
                avertissements.append(
                    f"{sid} : semaine JSON={semaine_json} mais recalculée={semaine_calc} "
                    f"— valeur recalculée utilisée."
                )
            semaine = semaine_calc

            hh, mm = map(int, entry["debut"].split(":"))
            debut = datetime(y, m, d, hh, mm, tzinfo=TZ)

            fin = None
            if entry.get("fin"):
                fh, fm = map(int, entry["fin"].split(":"))
                fin = datetime(y, m, d, fh, fm, tzinfo=TZ)

            objectif = entry["objectif"]
            bilan = entry.get("bilan")
            blocages = entry.get("blocages")
            statut = entry["statut"]

            if dry_run:
                print(f"[dry-run] {sid} : {nom} / {session_date.isoformat()} {creneau} / "
                      f"{canal_nom} / statut={statut} -> insertion OK")
            else:
                await db.execute(
                    """INSERT INTO sessions
                       (member_id, wave_id, semaine, date, creneau, canal_id, canal_nom,
                        debut, fin, objectif, bilan, blocages, statut)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        member_id, wave_id, semaine, session_date.isoformat(), creneau,
                        canal_id, canal_nom, debut.isoformat(), fin.isoformat() if fin else None,
                        objectif, bilan, blocages, statut,
                    ),
                )
            stats["sessions"] += 1

        if not dry_run:
            await db.commit()
    finally:
        if db_ctx:
            await db_ctx.__aexit__(None, None, None)

    verbe = "seraient importée(s)" if dry_run else "importée(s)"
    print(f"\n{stats['sessions']} session(s) {verbe}, {stats['sessions_ignorees']} ignorée(s).\n")

    print("=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    for table, n in stats.items():
        print(f"  {table} : {n}")

    if avertissements:
        print(f"\nAVERTISSEMENTS ({len(avertissements)}) :")
        for a in avertissements:
            print(f"  - {a}")

    if erreurs:
        print(f"\nERREURS ({len(erreurs)}) — sessions non importées, à traiter manuellement :")
        for e in erreurs:
            print(f"  - {e}")
    else:
        print("\nAucune erreur.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="simule sans toucher la DB")
    parser.add_argument(
        "--clean", action="store_true",
        help="DESTRUCTEUR : vide sessions/members/coworking_channels/waves avant import (toute la base, pas juste la vague backfill)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.clean))
