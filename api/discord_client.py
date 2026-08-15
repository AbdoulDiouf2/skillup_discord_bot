import time

import httpx

from bot.config import ADMIN_ROLE_NAME, GUILD_ID, TOKEN

DISCORD_API_BASE = "https://discord.com/api/v10"
ROLES_CACHE_TTL_SECONDS = 300
MEMBERS_CACHE_TTL_SECONDS = 300
VOICE_CHANNELS_CACHE_TTL_SECONDS = 300
DISCORD_CHANNEL_TYPE_VOICE = 2

_http: httpx.AsyncClient | None = None
_roles_cache: dict[str, str] | None = None
_roles_cache_at: float = 0.0
_members_cache: list[dict] | None = None
_members_cache_at: float = 0.0
_voice_channels_cache: list[dict] | None = None
_voice_channels_cache_at: float = 0.0


class DiscordAPIError(Exception):
    """Panne ou erreur inattendue de l'API Discord (réseau, timeout, 429, 5xx) —
    ne doit jamais être confondue avec "pas admin" (403)."""


def init_http_client() -> None:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=DISCORD_API_BASE,
            headers={"Authorization": f"Bot {TOKEN}"},
            timeout=10.0,
        )


async def close_http_client() -> None:
    global _http, _roles_cache, _roles_cache_at, _members_cache, _members_cache_at
    global _voice_channels_cache, _voice_channels_cache_at
    if _http is not None:
        await _http.aclose()
        _http = None
    _roles_cache = None
    _roles_cache_at = 0.0
    _members_cache = None
    _members_cache_at = 0.0
    _voice_channels_cache = None
    _voice_channels_cache_at = 0.0


def _client() -> httpx.AsyncClient:
    if _http is None:
        raise DiscordAPIError("Client HTTP Discord non initialisé.")
    return _http


async def _get_role_id_to_name() -> dict[str, str]:
    """Retourne {role_id: role_name} pour la guild, avec cache mémoire (TTL 300s) —
    les rôles changent rarement, contrairement à l'appartenance d'un membre à un rôle."""
    global _roles_cache, _roles_cache_at

    if _roles_cache is not None and (time.monotonic() - _roles_cache_at) < ROLES_CACHE_TTL_SECONDS:
        return _roles_cache

    try:
        resp = await _client().get(f"/guilds/{GUILD_ID}/roles")
    except httpx.HTTPError as e:
        raise DiscordAPIError(f"Échec de connexion à l'API Discord (rôles) : {e}") from e

    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", "?")
        raise DiscordAPIError(f"Rate limit Discord (rôles) — retry_after={retry_after}s")
    if resp.status_code >= 400:
        raise DiscordAPIError(f"Erreur API Discord (rôles) : {resp.status_code} {resp.text}")

    roles = resp.json()
    _roles_cache = {r["id"]: r["name"] for r in roles}
    _roles_cache_at = time.monotonic()
    return _roles_cache


async def is_admin(discord_id: str) -> bool:
    """True si `discord_id` détient le rôle ADMIN_ROLE_NAME sur la guild.
    False si l'utilisateur n'est simplement pas membre de la guild (404).
    Lève DiscordAPIError sur toute panne réelle (jamais un False silencieux)."""
    role_id_to_name = await _get_role_id_to_name()
    admin_role_ids = {rid for rid, name in role_id_to_name.items() if name == ADMIN_ROLE_NAME}
    if not admin_role_ids:
        return False

    try:
        resp = await _client().get(f"/guilds/{GUILD_ID}/members/{discord_id}")
    except httpx.HTTPError as e:
        raise DiscordAPIError(f"Échec de connexion à l'API Discord (membre) : {e}") from e

    if resp.status_code == 404:
        return False
    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", "?")
        raise DiscordAPIError(f"Rate limit Discord (membre) — retry_after={retry_after}s")
    if resp.status_code >= 400:
        raise DiscordAPIError(f"Erreur API Discord (membre) : {resp.status_code} {resp.text}")

    member = resp.json()
    member_role_ids = set(member.get("roles", []))
    return bool(member_role_ids & admin_role_ids)


async def get_guild_members() -> list[dict]:
    """Retourne [{discord_id, username}] pour tous les membres de la guild — pagine
    tant qu'une page pleine (1000 résultats) revient. Cache mémoire (TTL 300s), même
    schéma que `_get_role_id_to_name`. Nécessite le Server Members Intent (privilégié)
    activé côté Developer Portal, sinon la liste renvoyée par Discord est incomplète."""
    global _members_cache, _members_cache_at

    if _members_cache is not None and (time.monotonic() - _members_cache_at) < MEMBERS_CACHE_TTL_SECONDS:
        return _members_cache

    members: list[dict] = []
    after: str | None = None
    while True:
        params: dict[str, int | str] = {"limit": 1000}
        if after is not None:
            params["after"] = after

        try:
            resp = await _client().get(f"/guilds/{GUILD_ID}/members", params=params)
        except httpx.HTTPError as e:
            raise DiscordAPIError(f"Échec de connexion à l'API Discord (membres) : {e}") from e

        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", "?")
            raise DiscordAPIError(f"Rate limit Discord (membres) — retry_after={retry_after}s")
        if resp.status_code >= 400:
            raise DiscordAPIError(f"Erreur API Discord (membres) : {resp.status_code} {resp.text}")

        page = resp.json()
        members.extend(
            {"discord_id": m["user"]["id"], "username": m["user"]["username"]}
            for m in page
            if not m["user"].get("bot", False)
        )

        if len(page) < 1000:
            break
        after = page[-1]["user"]["id"]

    _members_cache = members
    _members_cache_at = time.monotonic()
    return members


async def get_voice_channels() -> list[dict]:
    """Retourne [{channel_id, name}] pour tous les salons vocaux standards (type == 2)
    de la guild — GET /guilds/{id}/channels est une route standard (pas de pagination,
    pas d'intent privilégié requis). Cache mémoire (TTL 300s), même schéma que
    `get_guild_members`."""
    global _voice_channels_cache, _voice_channels_cache_at

    if (
        _voice_channels_cache is not None
        and (time.monotonic() - _voice_channels_cache_at) < VOICE_CHANNELS_CACHE_TTL_SECONDS
    ):
        return _voice_channels_cache

    try:
        resp = await _client().get(f"/guilds/{GUILD_ID}/channels")
    except httpx.HTTPError as e:
        raise DiscordAPIError(f"Échec de connexion à l'API Discord (salons) : {e}") from e

    if resp.status_code == 429:
        retry_after = resp.json().get("retry_after", "?")
        raise DiscordAPIError(f"Rate limit Discord (salons) — retry_after={retry_after}s")
    if resp.status_code >= 400:
        raise DiscordAPIError(f"Erreur API Discord (salons) : {resp.status_code} {resp.text}")

    channels = resp.json()
    voice_channels = [
        {"channel_id": c["id"], "name": c["name"]}
        for c in channels
        if c.get("type") == DISCORD_CHANNEL_TYPE_VOICE
    ]

    _voice_channels_cache = voice_channels
    _voice_channels_cache_at = time.monotonic()
    return voice_channels


async def send_dm(discord_id: str, content: str) -> bool:
    """Envoie un DM à `discord_id` — best-effort, jamais fatal (miroir de `_safe_dm`
    côté bot Discord). Renvoie False sur tout échec (DMs fermés, compte introuvable,
    panne réseau) : l'appelant décide s'il veut le signaler à l'utilisateur, mais
    l'action métier (créer/retirer un binôme) ne doit jamais échouer à cause d'un DM."""
    try:
        channel_resp = await _client().post("/users/@me/channels", json={"recipient_id": discord_id})
        if channel_resp.status_code >= 400:
            return False
        channel_id = channel_resp.json()["id"]

        message_resp = await _client().post(
            f"/channels/{channel_id}/messages", json={"content": content}
        )
        return message_resp.status_code < 400
    except httpx.HTTPError:
        return False
