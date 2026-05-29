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

    def __init__(
        self,
        movies_df: pd.DataFrame,
        positive_threshold: float = 4.0,
        max_features: int = 30000,
        ngram_range: tuple[int, int] = (1, 2),
        use_weighted_fields: bool = True,
    ):
        super().__init__(movies_df)
        self.positive_threshold = positive_threshold
        self.max_features = max_features
        self.ngram_range = tuple(ngram_range)
        self.use_weighted_fields = use_weighted_fields
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=max_features, ngram_range=self.ngram_range)
        self.tfidf_matrix = None
        self.movie_ids: list[int] = []
        self.movie_to_idx: dict[int, int] = {}
        self.user_likes: dict[int, dict[int, float]] = defaultdict(dict)
        self.user_seen: dict[int, set[int]] = defaultdict(set)
        self.user_top: dict[int, list[int]] = defaultdict(list)
        self.movie_pop_rank: list[int] = []
        self.nn = None

    def _weighted_texts(self, df: pd.DataFrame) -> list[str]:
        if not self.use_weighted_fields:
            return df.get("metadata_text", pd.Series([""] * len(df))).fillna("").astype(str).tolist()
        parts = []
        for row in df.fillna("").itertuples(index=False):
            data = row._asdict()
            text = " ".join(
                [
                    (str(data.get("genres", "")) + " ") * 3,
                    (str(data.get("tag_text", "")) + " ") * 3,
                    (str(data.get("keywords", "")) + " ") * 2,
                    str(data.get("overview", "")),
                    str(data.get("cast", "")),
                    str(data.get("director", "")),
                ]
            )
            parts.append(text.lower())
        return parts

    def fit(self, train_ratings: pd.DataFrame | None = None) -> None:
        df = self.movies_df.fillna("")
        self.tfidf_matrix = self.vectorizer.fit_transform(self._weighted_texts(df))
        self.movie_ids = df["movieId"].astype(int).tolist()
        self.movie_to_idx = {mid: i for i, mid in enumerate(self.movie_ids)}
        self.nn = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=min(80, len(self.movie_ids)))
        self.nn.fit(self.tfidf_matrix)
        if train_ratings is not None and not train_ratings.empty:
            for row in train_ratings.itertuples(index=False):
                uid = int(row.userId)
                mid = int(row.movieId)
                rating = float(row.rating)
                self.user_seen[uid].add(mid)
                if rating >= self.positive_threshold:
                    self.user_likes[uid][mid] = max(rating - 3.0, 0.1)
            self.user_top = defaultdict(list)
            ranked = train_ratings.sort_values(["userId", "rating"], ascending=[True, False])
            for uid, grp in ranked.groupby("userId"):
                self.user_top[int(uid)] = grp["movieId"].astype(int).head(10).tolist()
        self.movie_pop_rank = self.movies_df.sort_values(["vote_count", "vote_average"], ascending=False)["movieId"].astype(int).tolist()

    def _profile_vector(self, user_id: int):
        if self.tfidf_matrix is None:
            return None
        liked = self.user_likes.get(user_id, {})
        if not liked:
            top = [mid for mid in self.user_top.get(user_id, []) if mid in self.movie_to_idx]
            liked = {mid: 1.0 for mid in top[:3]}
        idx_weights = [(self.movie_to_idx[mid], w) for mid, w in liked.items() if mid in self.movie_to_idx]
        if not idx_weights:
            return None
        idx = [i for i, _ in idx_weights]
        weights = np.array([w for _, w in idx_weights], dtype=float)
        weights = weights / (weights.sum() + 1e-12)
        profile_arr = weights @ self.tfidf_matrix[idx].toarray()
        return csr_matrix(profile_arr)

    def score(self, user_id: int, movie_id: int) -> float:
        if self.tfidf_matrix is None or movie_id not in self.movie_to_idx:
            return 0.0
        profile = self._profile_vector(user_id)
        if profile is None:
            return 0.0
        target_idx = self.movie_to_idx[movie_id]
        return float(cosine_similarity(profile, self.tfidf_matrix[target_idx]).ravel()[0])

    def score_items(self, user_id: int, movie_ids: list[int]) -> dict[int, float]:
        if self.tfidf_matrix is None:
            return {int(mid): 0.0 for mid in movie_ids}
        profile = self._profile_vector(user_id)
        if profile is None:
            return {int(mid): 0.0 for mid in movie_ids}
        mids = [int(mid) for mid in movie_ids]
        valid = [(mid, self.movie_to_idx[mid]) for mid in mids if mid in self.movie_to_idx]
        out = {mid: 0.0 for mid in mids}
        if valid:
            sims = cosine_similarity(profile, self.tfidf_matrix[[idx for _, idx in valid]]).ravel()
            for (mid, _), score in zip(valid, sims):
                out[mid] = float(score)
        return out

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        if self.tfidf_matrix is None:
            return []
        seen = self.user_seen.get(user_id, set()) if exclude_seen else set()
        profile = self._profile_vector(user_id)
        if profile is None:
            cold = [mid for mid in self.movie_pop_rank if mid not in seen][:top_k]
            return [self._format_movie(mid, 0.0, "Popular fallback for sparse content profile", reason_type="content_fallback", score_breakdown={"content": 0.0}) for mid in cold]
        sims = cosine_similarity(profile, self.tfidf_matrix).ravel()
        order = np.argsort(-sims)
        out: list[dict] = []
        for idx in order:
            mid = self.movie_ids[int(idx)]
            if mid in seen:
                continue
            score = float(sims[idx])
            out.append(
                self._format_movie(
                    mid,
                    score,
                    "Similar genres, tags, and story elements",
                    reason_type="content",
                    evidence="TF-IDF profile from training-set liked movies matches this movie's metadata.",
                    score_breakdown={"content": score},
                )
            )
            if len(out) >= top_k:
                break
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        if self.nn is None or movie_id not in self.movie_to_idx:
            return []
        idx = self.movie_to_idx[movie_id]
        distances, indices = self.nn.kneighbors(self.tfidf_matrix[idx], n_neighbors=min(top_k + 1, len(self.movie_ids)))
        title = self.movie_meta.get(movie_id, {}).get("title", "this movie")
        out = []
        for dist, nb_idx in zip(distances[0], indices[0]):
            mid = self.movie_ids[int(nb_idx)]
            if mid == movie_id:
                continue
            score = 1.0 - float(dist)
            out.append(self._format_movie(mid, score, f"Content-similar to {title}", reason_type="content", evidence="Similar genres, tags, keywords, and overview text.", score_breakdown={"content": score}))
            if len(out) >= top_k:
                break
        return out

    def discover_by_preferences(self, genres=None, keywords=None, year_range=None, top_k: int = 12) -> list[dict]:
        df = self.movies_df.copy()
        if genres:
            genres_lower = [g.lower() for g in genres]
            df = df[df["genres"].fillna("").str.lower().apply(lambda x: any(g in x for g in genres_lower))]
        if keywords:
            kw_lower = [k.lower() for k in keywords]
            text_col = df.get("metadata_text", df.get("overview", "")).fillna("").str.lower()
            df = df[text_col.apply(lambda x: any(k in x for k in kw_lower))]
        if year_range:
            y_min, y_max = year_range
            if y_min is not None:
                df = df[pd.to_numeric(df["year"], errors="coerce") >= y_min]
            if y_max is not None:
                df = df[pd.to_numeric(df["year"], errors="coerce") <= y_max]
        df = df.sort_values(["vote_average", "vote_count", "popularity"], ascending=False)
        return [self._format_movie(int(row.movieId), float(getattr(row, "vote_average", 0) or 0), "Matches your cold-start preferences", reason_type="content") for row in df.head(top_k).itertuples(index=False)]
