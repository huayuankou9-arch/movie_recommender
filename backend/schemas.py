from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MovieCard(BaseModel):
    movieId: int
    title: str
    year: int | None = None
    genres: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    overview: str | None = None
    score: float | None = None
    reason: str | None = None


class HomeResponse(BaseModel):
    hero_movie: dict[str, Any] | None
    for_you: list[dict[str, Any]]
    trending: list[dict[str, Any]]
    highly_rated: list[dict[str, Any]]
    because_you_like: list[dict[str, Any]]
    genre_rows: list[dict[str, Any]]
