from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.base import BaseRecommender


class PopularityRecommender(BaseRecommender):
    name = "popularity"

    def __init__(self, movies_df: pd.DataFrame, min_rating_count: int = 20):
        super().__init__(movies_df)
        self.min_rating_count = min_rating_count
        self.pop_scores: dict[int, float] = {}
        self.highly_rated: list[int] = []
        self.trending: list[int] = []

    def fit(self, train_ratings: pd.DataFrame) -> None:
        stats = (
            train_ratings.groupby("movieId")["rating"]
            .agg(avg_rating="mean", rating_count="count")
            .reset_index()
        )
        if stats.empty:
            return
        stats["log_count"] = np.log1p(stats["rating_count"])
        stats["avg_norm"] = (stats["avg_rating"] - stats["avg_rating"].min()) / (
            stats["avg_rating"].max() - stats["avg_rating"].min() + 1e-8
        )
        stats["count_norm"] = (stats["log_count"] - stats["log_count"].min()) / (
            stats["log_count"].max() - stats["log_count"].min() + 1e-8
        )
        stats["pop_score"] = 0.6 * stats["avg_norm"] + 0.4 * stats["count_norm"]
        qualified = stats[stats["rating_count"] >= self.min_rating_count].copy()
        if qualified.empty:
            qualified = stats.copy()
        self.pop_scores = {
            int(r.movieId): float(r.pop_score) for r in qualified.itertuples(index=False)
        }
        self.trending = (
            qualified.sort_values(["pop_score", "rating_count"], ascending=False)["movieId"]
            .astype(int)
            .tolist()
        )
        self.highly_rated = (
            qualified.sort_values(["avg_rating", "rating_count"], ascending=False)["movieId"]
            .astype(int)
            .tolist()
        )

    def score(self, user_id: int, movie_id: int) -> float:
        return float(self.pop_scores.get(int(movie_id), 0.0))

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        movie_ids = self.trending[:top_k]
        return [
            self._format_movie(mid, self.score(user_id, mid), "近期高分热门电影")
            for mid in movie_ids
        ]

    def recommend_trending(self, top_k: int = 12) -> list[dict]:
        return [self._format_movie(mid, self.pop_scores.get(mid, 0.0), "评分人数较多且平均评分较高") for mid in self.trending[:top_k]]

    def recommend_highly_rated(self, top_k: int = 12) -> list[dict]:
        return [self._format_movie(mid, self.pop_scores.get(mid, 0.0), "评分人数较多且平均评分较高") for mid in self.highly_rated[:top_k]]
