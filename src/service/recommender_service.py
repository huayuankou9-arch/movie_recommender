from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models.content_based import ContentBasedRecommender
from src.models.hybrid import HybridRecommender
from src.models.itemcf import ItemCFRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.popularity import PopularityRecommender
from src.models.usercf import UserCFRecommender
from src.utils.io import read_yaml


class RecommenderService:
    _instance = None

    def __init__(self):
        self.cfg = read_yaml("config.yaml")
        self.processed_dir = Path(self.cfg["data"]["processed_dir"])
        self.models_dir = Path(self.cfg["data"]["output_dir"]) / "models"
        self.movies_df = pd.read_csv(self.processed_dir / "movies_enriched.csv")
        self.movie_lookup = self.movies_df.set_index("movieId").to_dict("index")
        self.default_poster = self.cfg.get("app", {}).get("default_poster", "/placeholder-poster.png")
        self.default_backdrop = self.cfg.get("app", {}).get("default_backdrop", None)
        self.train_df = pd.read_csv(self.processed_dir / "train_ratings.csv")
        self.popularity = PopularityRecommender.load(self.models_dir / "popularity.pkl")
        self.usercf = UserCFRecommender.load(self.models_dir / "usercf.pkl")
        self.itemcf = ItemCFRecommender.load(self.models_dir / "itemcf.pkl")
        self.mf = MatrixFactorizationRecommender.load(self.models_dir / "mf.pkl")
        self.content = ContentBasedRecommender.load(self.models_dir / "content.pkl")
        self.hybrid = HybridRecommender.load(self.models_dir / "hybrid.pkl")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _norm_card(self, item: dict) -> dict:
        mid = int(item.get("movieId"))
        meta = self.movie_lookup.get(mid, {})
        poster_url = item.get("poster_url") or meta.get("poster_url") or self.default_poster
        backdrop_url = item.get("backdrop_url") or meta.get("backdrop_url") or self.default_backdrop
        if not isinstance(poster_url, str) or not poster_url.strip():
            poster_url = self.default_poster
        if isinstance(backdrop_url, str) and not backdrop_url.strip():
            backdrop_url = None
        return {
            **item,
            "movieId": mid,
            "title": item.get("title") or meta.get("title") or "Unknown Movie",
            "year": int(item["year"]) if item.get("year") is not None and pd.notna(item.get("year")) else (int(meta["year"]) if pd.notna(meta.get("year")) else None),
            "genres": item.get("genres") or meta.get("genres") or "",
            "overview": item.get("overview") or meta.get("overview") or "",
            "poster_url": poster_url,
            "backdrop_url": backdrop_url,
        }

    def _norm_list(self, items: list[dict]) -> list[dict]:
        return [self._norm_card(it) for it in items or []]

    def recommend(self, user_id: int, model: str = "hybrid", top_k: int = 12) -> list[dict]:
        model = model.lower()
        if model == "popularity":
            return self._norm_list(self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "usercf":
            recs = self.usercf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._norm_list(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "itemcf":
            recs = self.itemcf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._norm_list(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "mf":
            recs = self.mf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._norm_list(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "content":
            recs = self.content.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._norm_list(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        recs = self.hybrid.recommend(user_id, top_k=top_k, exclude_seen=True)
        return self._norm_list(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))

    def _genre_rows(self, user_id: int, top_k: int = 12) -> list[dict]:
        genres = (
            self.movies_df["genres"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .value_counts()
            .head(6)
            .index.tolist()
        )
        rows = []
        for g in genres:
            subset = self.movies_df[self.movies_df["genres"].fillna("").str.contains(g, case=False, regex=False)]
            subset = subset.sort_values(["vote_count", "vote_average"], ascending=False).head(top_k)
            movies = []
            for row in subset.itertuples(index=False):
                movies.append(
                    self._norm_card(
                        {
                            "movieId": int(row.movieId),
                            "title": row.title,
                            "year": int(row.year) if pd.notna(row.year) else None,
                            "genres": row.genres,
                            "poster_url": row.poster_url,
                            "backdrop_url": row.backdrop_url,
                            "overview": row.overview,
                            "score": float(row.vote_average) if pd.notna(row.vote_average) else 0.0,
                            "reason": f"{g} 类型精选",
                        }
                    )
                )
            rows.append({"genre": g, "movies": movies})
        return rows

    def home(self, user_id: int) -> dict:
        for_you = self.recommend(user_id=user_id, model="hybrid", top_k=12)
        hero = for_you[0] if for_you else None
        trending = self._norm_list(self.popularity.recommend_trending(12))
        highly_rated = self._norm_list(self.popularity.recommend_highly_rated(12))
        because = self._norm_list(self.itemcf.recommend(user_id=user_id, top_k=12, exclude_seen=True))
        if not because:
            because = self._norm_list(self.content.recommend(user_id=user_id, top_k=12, exclude_seen=True))
        genre_rows = self._genre_rows(user_id, top_k=12)
        return {
            "hero_movie": hero,
            "for_you": for_you,
            "trending": trending,
            "highly_rated": highly_rated,
            "because_you_like": because,
            "genre_rows": genre_rows,
        }

    def similar_movies(self, movie_id: int, method: str = "hybrid", top_k: int = 12) -> list[dict]:
        method = method.lower()
        if method == "itemcf":
            return self._norm_list(self.itemcf.similar_movies(movie_id, top_k=top_k))
        if method == "content":
            return self._norm_list(self.content.similar_movies(movie_id, top_k=top_k))
        if method == "mf":
            return self._norm_list(self.mf.similar_movies(movie_id, top_k=top_k))
        return self._norm_list(self.hybrid.similar_movies(movie_id, top_k=top_k))

    def discover(
        self,
        genres: list[str] | None = None,
        keywords: list[str] | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        top_k: int = 12,
    ) -> list[dict]:
        return self._norm_list(
            self.content.discover_by_preferences(
                genres=genres,
                keywords=keywords,
                year_range=(year_min, year_max),
                top_k=top_k,
            )
        )

    def algorithm_lab(self, user_id: int, top_k: int, weights: dict[str, float] | None = None) -> dict:
        res = {
            "popularity": self.recommend(user_id, "popularity", top_k),
            "usercf": self.recommend(user_id, "usercf", top_k),
            "itemcf": self.recommend(user_id, "itemcf", top_k),
            "mf": self.recommend(user_id, "mf", top_k),
            "content": self.recommend(user_id, "content", top_k),
        }
        if weights:
            temp_hybrid = HybridRecommender(
                self.movies_df,
                self.popularity,
                self.usercf,
                self.itemcf,
                self.mf,
                self.content,
                weights=weights,
            )
            res["hybrid"] = self._norm_list(temp_hybrid.recommend(user_id, top_k=top_k, exclude_seen=True))
        else:
            res["hybrid"] = self.recommend(user_id, "hybrid", top_k)
        return res

