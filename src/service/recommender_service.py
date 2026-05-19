from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from src.models.content_based import ContentBasedRecommender
from src.models.hybrid import HybridRecommender
from src.models.itemcf import ItemCFRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.popularity import PopularityRecommender
from src.models.usercf import UserCFRecommender
from src.utils.io import read_json, read_yaml


class RecommenderService:
    _instance = None

    def __init__(self):
        self.cfg = read_yaml("config.yaml")
        self.processed_dir = Path(self.cfg["data"]["processed_dir"])
        self.models_dir = Path(self.cfg["data"]["output_dir"]) / "models"
        self.poster_cache_path = Path(self.cfg["data"]["output_dir"]) / "cache" / "poster_repair_cache.json"
        self._poster_cache_mtime = None
        self._poster_cache_movies: dict[str, dict] = {}
        self.movies_df = pd.read_csv(self.processed_dir / "movies_enriched.csv")
        self.movie_lookup = self.movies_df.set_index("movieId").to_dict("index")
        self.default_poster = self.cfg.get("app", {}).get("default_poster", "https://placehold.co/500x750?text=No+Poster")
        self.default_backdrop = self.cfg.get("app", {}).get(
            "default_backdrop", "https://placehold.co/1200x675?text=No+Backdrop"
        )
        self.train_df = pd.read_csv(self.processed_dir / "train_ratings.csv")
        self.popularity = PopularityRecommender.load(self.models_dir / "popularity.pkl")
        self.usercf = UserCFRecommender.load(self.models_dir / "usercf.pkl")
        self.itemcf = ItemCFRecommender.load(self.models_dir / "itemcf.pkl")
        self.mf = MatrixFactorizationRecommender.load(self.models_dir / "mf.pkl")
        self.content = ContentBasedRecommender.load(self.models_dir / "content.pkl")
        self.hybrid = HybridRecommender.load(self.models_dir / "hybrid.pkl")

    def _refresh_poster_cache(self) -> None:
        if not self.poster_cache_path.exists():
            self._poster_cache_movies = {}
            self._poster_cache_mtime = None
            return
        mtime = self.poster_cache_path.stat().st_mtime
        if self._poster_cache_mtime == mtime:
            return
        try:
            payload = read_json(self.poster_cache_path)
            movies = payload.get("movies", {}) if isinstance(payload, dict) else {}
            self._poster_cache_movies = movies if isinstance(movies, dict) else {}
            self._poster_cache_mtime = mtime
        except Exception:
            self._poster_cache_movies = {}
            self._poster_cache_mtime = mtime

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def recommend(self, user_id: int, model: str = "hybrid", top_k: int = 12) -> list[dict]:
        model = model.lower()
        if model == "popularity":
            return self._hydrate_cards(self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "usercf":
            recs = self.usercf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._hydrate_cards(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "itemcf":
            recs = self.itemcf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._hydrate_cards(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "mf":
            recs = self.mf.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._hydrate_cards(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        if model == "content":
            recs = self.content.recommend(user_id, top_k=top_k, exclude_seen=True)
            return self._hydrate_cards(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))
        recs = self.hybrid.recommend(user_id, top_k=top_k, exclude_seen=True)
        return self._hydrate_cards(recs or self.popularity.recommend(user_id, top_k=top_k, exclude_seen=True))

    def home(self, user_id: int) -> dict:
        for_you = self.recommend(user_id=user_id, model="hybrid", top_k=12)
        hero = for_you[0] if for_you else None
        trending = self._hydrate_cards(self.popularity.recommend_trending(12))
        highly_rated = self._hydrate_cards(self.popularity.recommend_highly_rated(12))
        because = self._hydrate_cards(self.itemcf.recommend(user_id=user_id, top_k=12, exclude_seen=True))
        if not because:
            because = self._hydrate_cards(self.content.recommend(user_id=user_id, top_k=12, exclude_seen=True))
        genre_rows = self._genre_rows(user_id, top_k=12)
        return {
            "hero_movie": hero,
            "for_you": for_you,
            "trending": trending,
            "highly_rated": highly_rated,
            "because_you_like": because,
            "genre_rows": genre_rows,
        }

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
            rows.append({"genre": g, "movies": movies})
        return rows

    def similar_movies(self, movie_id: int, method: str = "hybrid", top_k: int = 12) -> list[dict]:
        method = method.lower()
        if method == "itemcf":
            return self._hydrate_cards(self.itemcf.similar_movies(movie_id, top_k=top_k))
        if method == "content":
            return self._hydrate_cards(self.content.similar_movies(movie_id, top_k=top_k))
        if method == "mf":
            return self._hydrate_cards(self.mf.similar_movies(movie_id, top_k=top_k))
        return self._hydrate_cards(self.hybrid.similar_movies(movie_id, top_k=top_k))

    def discover(
        self,
        genres: list[str] | None = None,
        keywords: list[str] | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        top_k: int = 12,
    ) -> list[dict]:
        return self._hydrate_cards(
            self.content.discover_by_preferences(
            genres=genres, keywords=keywords, year_range=(year_min, year_max), top_k=top_k
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
            res["hybrid"] = self._hydrate_cards(temp_hybrid.recommend(user_id, top_k=top_k, exclude_seen=True))
        else:
            res["hybrid"] = self.recommend(user_id, "hybrid", top_k)
        for key in ["popularity", "usercf", "itemcf", "mf", "content"]:
            res[key] = self._hydrate_cards(res[key])
        return res

    @staticmethod
    def _is_valid_image_url(url: str | None) -> bool:
        if not isinstance(url, str) or not url.strip():
            return False
        pattern = r"^https://image\.tmdb\.org/t/p/[^/]+/[^/]+\.(jpg|jpeg|png|webp)$"
        if re.match(pattern, url.strip(), flags=re.IGNORECASE):
            return True
        return "placehold.co" in url

    def _hydrate_cards(self, items: list[dict]) -> list[dict]:
        self._refresh_poster_cache()
        out: list[dict] = []
        def _pick(*values):
            for v in values:
                if v is None:
                    continue
                try:
                    if pd.isna(v):
                        continue
                except Exception:
                    pass
                if isinstance(v, str) and not v.strip():
                    continue
                return v
            return None

        for item in items:
            mid = int(item.get("movieId"))
            meta = self.movie_lookup.get(mid, {})
            repaired = self._poster_cache_movies.get(str(mid), {})
            title = _pick(item.get("title"), meta.get("title"), "Unknown Movie")
            year = _pick(item.get("year"), meta.get("year"))
            poster_url = _pick(repaired.get("poster_url"), item.get("poster_url"), meta.get("poster_url"))
            backdrop_url = _pick(repaired.get("backdrop_url"), item.get("backdrop_url"), meta.get("backdrop_url"))
            if not self._is_valid_image_url(poster_url):
                poster_url = self.default_poster
            if not self._is_valid_image_url(backdrop_url):
                backdrop_url = self.default_backdrop
            out.append(
                {
                    **item,
                    "title": title,
                    "year": int(year) if year is not None and not pd.isna(year) else None,
                    "genres": _pick(item.get("genres"), meta.get("genres"), ""),
                    "overview": _pick(item.get("overview"), meta.get("overview"), ""),
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                }
            )
        return out
