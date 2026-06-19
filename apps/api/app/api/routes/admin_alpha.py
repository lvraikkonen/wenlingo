from fastapi import APIRouter

from app.api.admin_alpha_routes import accounts, ai_usage, invites, overview
from app.api.admin_alpha_routes.invites import (
    _generate_invite_code,
    _generate_unique_invite_code,
    hash_invite_code,
)

router = APIRouter(prefix="/api/admin/alpha", tags=["admin-alpha"])
router.include_router(invites.router)
router.include_router(accounts.router)
router.include_router(ai_usage.router)
router.include_router(overview.router)

__all__ = [
    "_generate_invite_code",
    "_generate_unique_invite_code",
    "hash_invite_code",
    "router",
]
