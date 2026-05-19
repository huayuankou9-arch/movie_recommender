from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors

from src.models.base import BaseRecommender


class ItemCFRecommender(BaseRecommender):
    name = "itemcf"

    def __init__(self, movies_df: pd.DataFrame, top_n_similar: int = 50):
        super().__init__(movies_df)
        self.top_n_similar = top_n_similar
        self.matrix: csr_matrix | None = None
        self.user_to_idx: dict[int, int] = {}
        self.idx_to_user: dict[int, int] = {}
        self.movie_to_idx: dict[int, int] = {}
        self.idx_to_movie: dict[int, int] = {}
        self.neighbors: dict[int, list[tuple[int, float]]] = defaultdict(list)
        self.user_rated: dict[int, dict[int, float]] = defaultdict(dict)

    def fit(self, train_ratings: pd.DataFrame, matrix_bundle: dict[str, object]) -> None:
        self.matrix = matrix_bundle["matrix"]
        user_encoder = matrix_bundle["user_encoder"]
        movie_encoder = matrix_bundle["movie_encoder"]
        self.user_to_idx = {int(uid): int(i) for i, uid in enumerate(user_encoder.classes_)}
        self.idx_to_user = {v: k for k, v in self.user_to_idx.items()}
        self.movie_to_idx = {int(mid): int(i) for i, mid in enumerate(movie_encoder.classes_)}
        self.idx_to_movie = {v: k for k, v in self.movie_to_idx.items()}

        item_matrix = self.matrix.T.tocsr()
        n_neighbors = min(self.top_n_similar + 1, item_matrix.shape[0])
        nn = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=n_neighbors)
        nn.fit(item_matrix)
        distances, indices = nn.kneighbors(item_matrix, return_distance=True)
        for item_idx in range(item_matrix.shape[0]):
            mid = self.idx_to_movie[item_idx]
            nbs: list[tuple[int, float]] = []
            for dist, idx in zip(distances[item_idx], indices[item_idx]):
                if idx == item_idx:
                    continue
                sim = 1.0 - float(dist)
                if sim <= 0:
                    continue
                nbs.append((self.idx_to_movie[int(idx)], sim))
            self.neighbors[mid] = nbs[: self.top_n_similar]

        for row in train_ratings.itertuples(index=False):
            self.user_rated[int(row.userId)][int(row.movieId)] = float(row.rating)

    def score(self, user_id: int, movie_id: int) -> float:
        rated = self.user_rated.get(user_id, {})
        if not rated:
            return 0.0
        score = 0.0
        for src_mid, r in rated.items():
            for nb_mid, sim in self.neighbors.get(src_mid, []):
                if nb_mid == movie_id:
                    score += sim * r
        return float(score)

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        rated = self.user_rated.get(user_id, {})
        if not rated:
            return []
        seen = set(rated.keys()) if exclude_seen else set()
        candidate_scores: dict[int, float] = defaultdict(float)
        reason_source: dict[int, tuple[int, float]] = {}
        for src_mid, src_rating in rated.items():
            for nb_mid, sim in self.neighbors.get(src_mid, []):
                if nb_mid in seen:
                    continue
                contrib = sim * src_rating
                candidate_scores[nb_mid] += contrib
                prev = reason_source.get(nb_mid)
                if prev is None or contrib > prev[1]:
                    reason_source[nb_mid] = (src_mid, contrib)
        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        out: list[dict] = []
        for mid, s in ranked:
            src_mid = reason_source.get(mid, (None, 0))[0]
            src_title = self.movie_meta.get(src_mid, {}).get("title", "某部电影")
            out.append(self._format_movie(mid, s, f"因为你喜欢《{src_title}》"))
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        sims = self.neighbors.get(movie_id, [])[:top_k]
        return [self._format_movie(mid, sim, "与该电影在评分行为上相似") for mid, sim in sims]
