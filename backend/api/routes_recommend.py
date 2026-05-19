from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.service.recommender_service import RecommenderService
from src.utils.json_utils import sanitize_for_json

router = APIRouter(prefix="/api", tags=["recommend"])


@router.get("/recommend/{user_id}")
def recommend(user_id: int, model: str = Query("hybrid"), top_k: int = Query(12)):
    try:
        svc = RecommenderService.get_instance()
        return sanitize_for_json(
            {"user_id": user_id, "model": model, "top_k": top_k, "items": svc.recommend(user_id, model, top_k)}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to recommend: {exc}") from exc


@router.get("/algorithm-lab")
def algorithm_lab(
    user_id: int = Query(1),
    top_k: int = Query(12),
    popularity: float = Query(0.10),
    usercf: float = Query(0.20),
    itemcf: float = Query(0.25),
    mf: float = Query(0.30),
    content: float = Query(0.15),
):
    try:
        svc = RecommenderService.get_instance()
        weights = {
            "popularity": popularity,
            "usercf": usercf,
            "itemcf": itemcf,
            "mf": mf,
            "content": content,
        }
        s = sum(weights.values())
        if s > 0:
            weights = {k: v / s for k, v in weights.items()}
        return sanitize_for_json(
            {
                "user_id": user_id,
                "top_k": top_k,
                "weights": weights,
                "results": svc.algorithm_lab(user_id, top_k, weights),
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed in algorithm lab: {exc}") from exc
