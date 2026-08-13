import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"]) if os.environ.get("GUILD_ID") else None
DB_PATH = Path(os.environ.get("DB_PATH", "data/skillup.db"))

TZ = ZoneInfo("Europe/Paris")

CRENEAUX = ("5h-7h", "19h-21h", "21h-23h")
ADMIN_ROLE_NAME = "Admin SkillUp"
