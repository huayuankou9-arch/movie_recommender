from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.service.movie_service import MovieService
from src.service.recommender_service import RecommenderService
from src.utils.json_utils import sanitize_for_json

router = APIRouter(prefix="/api", tags=["movies"])


@router.get("/movies/{movie_id}")
def get_movie_detail(movie_id: int):
    try:
        movie = MovieService.get_instance().get_movie(movie_id)
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        similar = RecommenderService.get_instance().similar_movies(movie_id, method="hybrid", top_k=12)
        movie["similar_movies"] = similar
        return sanitize_for_json(movie)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch movie detail: {exc}") from exc


@router.get("/movies/{movie_id}/similar")
def similar_movies(movie_id: int, method: str = Query("hybrid"), top_k: int = Query(12)):
    try:
        items = RecommenderService.get_instance().similar_movies(movie_id, method=method, top_k=top_k)
        return sanitize_for_json({"movie_id": movie_id, "method": method, "items": items})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch similar movies: {exc}") from exc


@router.get("/discover")
def discover(
    genres: str = Query(""),
    keywords: str = Query(""),
    year_min: int | None = Query(None),
    year_max: int | None = Query(None),
    top_k: int = Query(12),
):
    try:
        genre_list = [x.strip() for x in genres.split(",") if x.strip()]
        kw_list = [x.strip() for x in keywords.split(",") if x.strip()]
        items = RecommenderService.get_instance().discover(
            genres=genre_list, keywords=kw_list, year_min=year_min, year_max=year_max, top_k=top_k
        )
        return sanitize_for_json({"items": items})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Discover failed: {exc}") from exc


@router.get("/search")
def search(q: str = Query(...), top_k: int = Query(20)):
    try:
        return sanitize_for_json({"items": MovieService.get_instance().search(q, top_k=top_k)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@router.post("/movies/{movie_id}/poster/repair")
def repair_poster(movie_id: int, current_url: str | None = Query(None), force: bool = Query(False)):
    try:
        payload = MovieService.get_instance().repair_poster(movie_id, current_url=current_url, force=force)
        return sanitize_for_json(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Poster repair failed: {exc}") from exc
