from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.service.recommender_service import RecommenderService
from src.utils.json_utils import sanitize_for_json

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home")
def get_home(user_id: int = Query(1)):
    try:
        svc = RecommenderService.get_instance()
        return sanitize_for_json(svc.home(user_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load home data: {exc}") from exc
