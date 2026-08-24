import os

# Importer bot.config en premier garantit que load_dotenv() a déjà tourné
# (ENV=dev|prod -> .env.dev/.env) avant qu'on lise API_KEY ci-dessous.
from bot.config import ADMIN_ROLE_NAME, GUILD_ID, TOKEN, TZ  # noqa: F401

if GUILD_ID is None:
    raise RuntimeError("GUILD_ID absent — requis par l'API pour la vérification du rôle Admin Discord.")

API_KEY = os.environ["API_KEY"]
# Optionnelles : l'assistant IA peut être désactivé (ai_settings.enabled) ou n'utiliser
# qu'un seul des deux providers — pas de raison de faire planter l'API entière si l'une
# des deux clés manque. L'erreur claire arrive au moment de l'appel, pas au démarrage.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
