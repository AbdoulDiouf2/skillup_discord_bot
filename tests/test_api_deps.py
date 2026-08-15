import pytest
from fastapi import HTTPException, Request

from api import deps
from api.discord_client import DiscordAPIError

pytestmark = pytest.mark.asyncio


def _fake_request(path_params: dict) -> Request:
    return Request({"type": "http", "path_params": path_params, "headers": []})


async def _admin_true(_discord_id: str) -> bool:
    return True


async def _admin_false(_discord_id: str) -> bool:
    return False


async def _admin_raises(_discord_id: str) -> bool:
    raise DiscordAPIError("panne simulée")


async def test_require_api_key_accepts_correct_key():
    from api.config import API_KEY

    await deps.require_api_key(x_api_key=API_KEY)  # ne lève pas


async def test_require_api_key_rejects_wrong_key():
    with pytest.raises(HTTPException) as exc:
        await deps.require_api_key(x_api_key="clé-invalide")
    assert exc.value.status_code == 401


async def test_require_admin_allows_admin(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_true)
    result = await deps.require_admin(caller_id="123", _key=None)
    assert result == "123"


async def test_require_admin_rejects_non_admin(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_false)
    with pytest.raises(HTTPException) as exc:
        await deps.require_admin(caller_id="123", _key=None)
    assert exc.value.status_code == 403


async def test_require_admin_discord_outage_returns_503(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_raises)
    with pytest.raises(HTTPException) as exc:
        await deps.require_admin(caller_id="123", _key=None)
    assert exc.value.status_code == 503


async def test_require_self_or_admin_allows_self():
    dependency = deps.require_self_or_admin()
    request = _fake_request({"discord_id": "123"})
    result = await dependency(request=request, caller_id="123")
    assert result == "123"


async def test_require_self_or_admin_admin_bypasses(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_true)
    dependency = deps.require_self_or_admin()
    request = _fake_request({"discord_id": "999"})
    result = await dependency(request=request, caller_id="123")
    assert result == "123"


async def test_require_self_or_admin_rejects_other_non_admin(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_false)
    dependency = deps.require_self_or_admin()
    request = _fake_request({"discord_id": "999"})
    with pytest.raises(HTTPException) as exc:
        await dependency(request=request, caller_id="123")
    assert exc.value.status_code == 403


async def test_require_self_or_admin_discord_outage_returns_503(monkeypatch):
    monkeypatch.setattr(deps.discord_client, "is_admin", _admin_raises)
    dependency = deps.require_self_or_admin()
    request = _fake_request({"discord_id": "999"})
    with pytest.raises(HTTPException) as exc:
        await dependency(request=request, caller_id="123")
    assert exc.value.status_code == 503
