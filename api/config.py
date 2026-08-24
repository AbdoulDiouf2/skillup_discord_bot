import os

# Importer bot.config en premier garantit que load_dotenv() a déjà tourné
# (ENV=dev|prod -> .env.dev/.env) avant qu'on lise API_KEY ci-dessous.
from bot.config import ADMIN_ROLE_NAME, GUILD_ID, TOKEN, TZ  # noqa: F401

if GUILD_ID is None:
    raise RuntimeError("GUILD_ID absent — requis par l'API pour la vérification du rôle Admin Discord.")

API_KEY = os.environ["API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
