from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request

from api import discord_client
from api.config import API_KEY
from api.discord_client import DiscordAPIError
from bot.db.database import Connection, get_connection


async def require_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(401, "Clé API invalide.")


async def get_caller_discord_id(x_discord_id: str = Header(...)) -> str:
    return x_discord_id


async def get_db() -> AsyncIterator[Connection]:
    async with get_connection() as db:
        yield db


async def _check_admin(caller_id: str) -> bool:
    try:
        return await discord_client.is_admin(caller_id)
    except DiscordAPIError as e:
        raise HTTPException(503, f"Impossible de vérifier le rôle Discord : {e}") from e


async def require_admin(
    caller_id: str = Depends(get_caller_discord_id),
    _key: None = Depends(require_api_key),
) -> str:
    if not await _check_admin(caller_id):
        raise HTTPException(403, "Réservé aux admins SkillUp.")
    return caller_id


def require_self_or_admin(path_param: str = "discord_id"):
    async def _dependency(
        request: Request,
        caller_id: str = Depends(get_caller_discord_id),
        _key: None = Depends(require_api_key),
    ) -> str:
        target_id = request.path_params[path_param]
        if caller_id == target_id:
            return caller_id
        if await _check_admin(caller_id):
            return caller_id
        raise HTTPException(403, "Tu ne peux consulter que tes propres données.")

    return _dependency
