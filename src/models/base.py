from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
import pandas as pd


@dataclass
class ModelState:
    payload: dict[str, Any]


class BaseRecommender:
    name = "base"

    def __init__(self, movies_df: pd.DataFrame):
        self.movies_df = movies_df.copy()
        self.movie_meta = self.movies_df.set_index("movieId").to_dict("index")

    def fit(self, *args, **kwargs) -> None:
        raise NotImplementedError

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        raise NotImplementedError

    def score(self, user_id: int, movie_id: int) -> float:
        raise NotImplementedError

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        return []

    def save(self, path: str) -> None:
        joblib.dump(self.__dict__, path)

    @classmethod
    def load(cls, path: str):
        state = joblib.load(path)
        obj = cls.__new__(cls)
        obj.__dict__.update(state)
        return obj

    def _format_movie(self, movie_id: int, score: float, reason: str) -> dict:
        meta = self.movie_meta.get(movie_id, {})
        return {
            "movieId": int(movie_id),
            "title": meta.get("title", ""),
            "year": int(meta["year"]) if pd.notna(meta.get("year")) else None,
            "genres": meta.get("genres", ""),
            "poster_url": meta.get("poster_url", ""),
            "backdrop_url": meta.get("backdrop_url", ""),
            "overview": meta.get("overview", ""),
            "score": float(np.round(score, 6)),
            "reason": reason,
        }
