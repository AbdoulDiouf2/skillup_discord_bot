import asyncio
import time

import httpx

from bot.config import ADMIN_ROLE_NAME, GUILD_ID, TOKEN

DISCORD_API_BASE = "https://discord.com/api/v10"
ROLES_CACHE_TTL_SECONDS = 300
MEMBERS_CACHE_TTL_SECONDS = 300
VOICE_CHANNELS_CACHE_TTL_SECONDS = 300
DISCORD_CHANNEL_TYPE_VOICE = 2
# Au-delà de ce délai, un retry ferait plus de mal (latence perçue) que de bien —
# on laisse remonter l'erreur telle quelle plutôt que de faire attendre l'appelant.
RETRY_AFTER_THRESHOLD_SECONDS = 2.0

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


async def _get_with_retry(
    url: str, params: dict | None, context: str, allow_404: bool = False
) -> httpx.Response:
    """GET avec un seul retry si Discord répond 429 avec un `retry_after` court (<
    RETRY_AFTER_THRESHOLD_SECONDS) — une panne transitoire de rate limit ne doit pas
    remonter en erreur si l'attente est négligeable. Au-delà du seuil, ou si le retry
    échoue aussi, lève `DiscordAPIError` — jamais de boucle, un seul essai de plus.
    `allow_404` : renvoie la réponse telle quelle sur 404 au lieu de lever (cas
    `is_admin`, où 404 = "pas membre de la guild", pas une panne)."""
    for attempt in range(2):
        try:
            resp = await _client().get(url, params=params)
        except httpx.HTTPError as e:
            raise DiscordAPIError(f"Échec de connexion à l'API Discord ({context}) : {e}") from e

        if allow_404 and resp.status_code == 404:
            return resp

        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after")
            if attempt == 0 and isinstance(retry_after, (int, float)) and retry_after < RETRY_AFTER_THRESHOLD_SECONDS:
                await asyncio.sleep(retry_after)
                continue
            raise DiscordAPIError(f"Rate limit Discord ({context}) — retry_after={retry_after}s")

        if resp.status_code >= 400:
            raise DiscordAPIError(f"Erreur API Discord ({context}) : {resp.status_code} {resp.text}")

        return resp

    raise DiscordAPIError(f"Rate limit Discord ({context}) persistant après retry.")


async def _get_role_id_to_name() -> dict[str, str]:
    """Retourne {role_id: role_name} pour la guild, avec cache mémoire (TTL 300s) —
    les rôles changent rarement, contrairement à l'appartenance d'un membre à un rôle."""
    global _roles_cache, _roles_cache_at

    if _roles_cache is not None and (time.monotonic() - _roles_cache_at) < ROLES_CACHE_TTL_SECONDS:
        return _roles_cache

    resp = await _get_with_retry(f"/guilds/{GUILD_ID}/roles", None, "rôles")
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

    resp = await _get_with_retry(
        f"/guilds/{GUILD_ID}/members/{discord_id}", None, "membre", allow_404=True
    )
    if resp.status_code == 404:
        return False

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

        resp = await _get_with_retry(f"/guilds/{GUILD_ID}/members", params, "membres")
        page = resp.json()
        members.extend(
            {
                "discord_id": m["user"]["id"],
                # Priorité au surnom serveur, puis au nom affiché Discord, puis au
                # pseudo (@handle) en dernier recours — c'est ce que les membres
                # voient réellement à l'écran, contrairement au pseudo technique.
                "username": m.get("nick") or m["user"].get("global_name") or m["user"]["username"],
            }
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

    resp = await _get_with_retry(f"/guilds/{GUILD_ID}/channels", None, "salons")
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
