from fastapi import APIRouter, Depends

from api.deps import get_caller_discord_id, get_db, require_api_key
from api.schemas import VagueAdminOut, VaguesListResponse
from bot.services.admin_service import resolve_vagues_lister

router = APIRouter(tags=["vagues"], dependencies=[Depends(require_api_key), Depends(get_caller_discord_id)])


@router.get("/vagues", response_model=VaguesListResponse)
async def get_vagues(statut: str | None = None, db=Depends(get_db)):
    """Liste toutes les vagues du système (pas seulement celles de l'appelant) —
    accessible à tout appelant authentifié, participant ou admin : lecture non sensible
    (nom/dates/statut de vague). Anciennement dans `api/routers/admin.py` derrière
    `require_admin` — migré ici pour que le sélecteur de vague partagé (participant +
    admin, `SkillUp.tsx`) puisse s'en servir sans 403 pour un participant non-admin.
    Les écritures (créer/activer/clôturer une vague) restent admin-only dans admin.py."""
    vagues = await resolve_vagues_lister(db, statut)
    return VaguesListResponse(vagues=[VagueAdminOut(**dict(v)) for v in vagues])
