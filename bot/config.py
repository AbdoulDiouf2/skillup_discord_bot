import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
_ENV = os.environ.get("ENV", "prod")
if _ENV not in ("dev", "prod"):
    raise ValueError(f"ENV doit valoir 'dev' ou 'prod', reçu : {_ENV!r}")
_ENV_FILE = _ROOT / (".env.dev" if _ENV == "dev" else ".env")
load_dotenv(_ENV_FILE)

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"]) if os.environ.get("GUILD_ID") else None
if "DATABASE_URL" not in os.environ:
    raise RuntimeError(
        f"DATABASE_URL absente de {_ENV_FILE.name} — "
        + (
            "l'environnement prod n'a pas encore été migré vers Postgres (voir .env.dev)."
            if _ENV == "prod"
            else "vérifie .env.dev."
        )
    )
DATABASE_URL = os.environ["DATABASE_URL"]

TZ = ZoneInfo("Europe/Paris")

CRENEAUX = ("5h-7h", "19h-21h", "21h-23h")
ADMIN_ROLE_NAME = "Admin SkillUp"
OBJECTIFS_FORUM_NAME = "objectifs"
