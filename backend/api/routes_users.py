from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.service.user_service import UserService
from src.utils.json_utils import sanitize_for_json

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users/{user_id}/profile")
def user_profile(user_id: int):
    try:
        profile = UserService.get_instance().user_profile(user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        return sanitize_for_json(profile)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build user profile: {exc}") from exc
