from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors

from src.models.base import BaseRecommender


class ContentBasedRecommender(BaseRecommender):
    name = "content"

    def __init__(self, movies_df: pd.DataFrame, positive_threshold: float = 4.0):
        super().__init__(movies_df)
        self.positive_threshold = positive_threshold
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=20000, ngram_range=(1, 2))
        self.tfidf_matrix = None
        self.movie_ids: list[int] = []
        self.movie_to_idx: dict[int, int] = {}
        self.user_likes: dict[int, set[int]] = defaultdict(set)
        self.movie_pop_rank: list[int] = []
        self.nn = None

    def fit(self, train_ratings: pd.DataFrame | None = None) -> None:
        df = self.movies_df.fillna("")
        texts = df["metadata_text"].astype(str).tolist()
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        self.movie_ids = df["movieId"].astype(int).tolist()
        self.movie_to_idx = {mid: i for i, mid in enumerate(self.movie_ids)}
        self.nn = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=min(60, len(self.movie_ids)))
        self.nn.fit(self.tfidf_matrix)
        if train_ratings is not None and not train_ratings.empty:
            for row in train_ratings.itertuples(index=False):
                if float(row.rating) >= self.positive_threshold:
                    self.user_likes[int(row.userId)].add(int(row.movieId))
        self.movie_pop_rank = (
            self.movies_df.sort_values(["vote_count", "vote_average"], ascending=False)["movieId"]
            .astype(int)
            .tolist()
        )

    def score(self, user_id: int, movie_id: int) -> float:
        if self.tfidf_matrix is None:
            return 0.0
        liked = self.user_likes.get(user_id, set())
        if not liked or movie_id not in self.movie_to_idx:
            return 0.0
        liked_idx = [self.movie_to_idx[mid] for mid in liked if mid in self.movie_to_idx]
        if not liked_idx:
            return 0.0
        target_idx = self.movie_to_idx[movie_id]
        sims = cosine_similarity(self.tfidf_matrix[target_idx], self.tfidf_matrix[liked_idx]).ravel()
        return float(np.mean(sims)) if len(sims) else 0.0

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        if self.tfidf_matrix is None:
            return []
        liked = self.user_likes.get(user_id, set())
        seen = liked if exclude_seen else set()
        if not liked:
            cold = [mid for mid in self.movie_pop_rank if mid not in seen][:top_k]
            return [
                self._format_movie(mid, 0.0, "类型、标签、剧情简介与你感兴趣主题相似")
                for mid in cold
            ]
        liked_idx = [self.movie_to_idx[mid] for mid in liked if mid in self.movie_to_idx]
        profile_arr = np.asarray(self.tfidf_matrix[liked_idx].mean(axis=0))
        profile = csr_matrix(profile_arr)
        sims = cosine_similarity(profile, self.tfidf_matrix).ravel()
        order = np.argsort(-sims)
        out: list[dict] = []
        for idx in order:
            mid = self.movie_ids[int(idx)]
            if mid in seen:
                continue
            out.append(self._format_movie(mid, float(sims[idx]), "类型、标签、剧情简介与你喜欢的电影相似"))
            if len(out) >= top_k:
                break
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        if self.nn is None or movie_id not in self.movie_to_idx:
            return []
        idx = self.movie_to_idx[movie_id]
        distances, indices = self.nn.kneighbors(self.tfidf_matrix[idx], n_neighbors=min(top_k + 1, len(self.movie_ids)))
        out = []
        for dist, nb_idx in zip(distances[0], indices[0]):
            mid = self.movie_ids[int(nb_idx)]
            if mid == movie_id:
                continue
            out.append(self._format_movie(mid, 1.0 - float(dist), "内容特征与该电影相似"))
            if len(out) >= top_k:
                break
        return out

    def discover_by_preferences(
        self,
        genres: list[str] | None = None,
        keywords: list[str] | None = None,
        year_range: tuple[int | None, int | None] | None = None,
        top_k: int = 12,
    ) -> list[dict]:
        df = self.movies_df.copy()
        if genres:
            genres_lower = [g.lower() for g in genres]
            mask = df["genres"].fillna("").str.lower().apply(lambda x: any(g in x for g in genres_lower))
            df = df[mask]
        if keywords:
            kw_lower = [k.lower() for k in keywords]
            mask = df["metadata_text"].fillna("").str.lower().apply(lambda x: any(k in x for k in kw_lower))
            df = df[mask]
        if year_range:
            y_min, y_max = year_range
            if y_min is not None:
                df = df[pd.to_numeric(df["year"], errors="coerce") >= y_min]
            if y_max is not None:
                df = df[pd.to_numeric(df["year"], errors="coerce") <= y_max]
        df = df.sort_values(["vote_average", "vote_count", "popularity"], ascending=False)
        return [
            self._format_movie(int(row.movieId), float(row.vote_average or 0), "根据你的类型与关键词偏好推荐")
            for row in df.head(top_k).itertuples(index=False)
        ]
