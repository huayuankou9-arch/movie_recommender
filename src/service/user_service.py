from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.io import read_yaml


class UserService:
    _instance = None

    def __init__(self):
        cfg = read_yaml("config.yaml")
        processed_dir = Path(cfg["data"]["processed_dir"])
        self.train_df = pd.read_csv(processed_dir / "train_ratings.csv")
        self.movies_df = pd.read_csv(processed_dir / "movies_enriched.csv")
        self.movie_map = self.movies_df.set_index("movieId").to_dict("index")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def user_profile(self, user_id: int) -> dict | None:
        user_r = self.train_df[self.train_df["userId"] == user_id].copy()
        if user_r.empty:
            return None
        rating_count = int(len(user_r))
        avg_rating = float(user_r["rating"].mean())
        merged = user_r.merge(self.movies_df[["movieId", "genres", "title", "poster_url", "year"]], on="movieId", how="left")
        genre_counts = (
            merged["genres"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .value_counts()
        )
        top_genres = genre_counts.head(5).index.tolist()

        top_rated = merged.sort_values(["rating", "timestamp"], ascending=[False, False]).head(12)
        recent = merged.sort_values("timestamp", ascending=False).head(12)

        summary = (
            f"该用户共评分 {rating_count} 部电影，平均评分 {avg_rating:.2f}。"
            f"偏好类型主要为：{', '.join(top_genres[:3]) if top_genres else '暂无明显偏好'}。"
        )
        return {
            "userId": int(user_id),
            "rating_count": rating_count,
            "avg_rating": round(avg_rating, 4),
            "favorite_genres": top_genres,
            "genre_distribution": [{"genre": g, "count": int(c)} for g, c in genre_counts.items()],
            "top_rated_movies": [
                {
                    "movieId": int(r.movieId),
                    "title": r.title,
                    "year": int(r.year) if pd.notna(r.year) else None,
                    "poster_url": r.poster_url,
                    "rating": float(r.rating),
                }
                for r in top_rated.itertuples(index=False)
            ],
            "recent_movies": [
                {
                    "movieId": int(r.movieId),
                    "title": r.title,
                    "year": int(r.year) if pd.notna(r.year) else None,
                    "poster_url": r.poster_url,
                    "rating": float(r.rating),
                }
                for r in recent.itertuples(index=False)
            ],
            "profile_summary": summary,
        }
