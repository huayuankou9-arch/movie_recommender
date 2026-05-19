from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

from src.models.base import BaseRecommender


class UserCFRecommender(BaseRecommender):
    name = "usercf"

    def __init__(self, movies_df: pd.DataFrame, top_k_neighbors: int = 30):
        super().__init__(movies_df)
        self.top_k_neighbors = top_k_neighbors
        self.user_sim: np.ndarray | None = None
        self.matrix: csr_matrix | None = None
        self.user_to_idx: dict[int, int] = {}
        self.idx_to_user: dict[int, int] = {}
        self.movie_to_idx: dict[int, int] = {}
        self.idx_to_movie: dict[int, int] = {}
        self.seen_by_user: dict[int, set[int]] = defaultdict(set)

    def fit(self, train_ratings: pd.DataFrame, matrix_bundle: dict[str, object]) -> None:
        self.matrix = matrix_bundle["matrix"]
        user_encoder = matrix_bundle["user_encoder"]
        movie_encoder = matrix_bundle["movie_encoder"]
        self.user_to_idx = {int(uid): int(i) for i, uid in enumerate(user_encoder.classes_)}
        self.idx_to_user = {v: k for k, v in self.user_to_idx.items()}
        self.movie_to_idx = {int(mid): int(i) for i, mid in enumerate(movie_encoder.classes_)}
        self.idx_to_movie = {v: k for k, v in self.movie_to_idx.items()}
        self.user_sim = cosine_similarity(self.matrix)
        np.fill_diagonal(self.user_sim, 0.0)
        for row in train_ratings.itertuples(index=False):
            self.seen_by_user[int(row.userId)].add(int(row.movieId))

    def _predict_idx(self, uidx: int, midx: int) -> float:
        if self.user_sim is None or self.matrix is None:
            return 0.0
        sims = self.user_sim[uidx]
        if sims.size == 0:
            return 0.0
        neighbor_idx = np.argpartition(-sims, min(self.top_k_neighbors, len(sims) - 1))[
            : self.top_k_neighbors
        ]
        ratings = self.matrix[neighbor_idx, midx].toarray().ravel()
        valid = ratings > 0
        if valid.sum() == 0:
            return 0.0
        n_sims = sims[neighbor_idx][valid]
        n_ratings = ratings[valid]
        den = np.sum(np.abs(n_sims)) + 1e-8
        return float(np.sum(n_sims * n_ratings) / den)

    def score(self, user_id: int, movie_id: int) -> float:
        if user_id not in self.user_to_idx or movie_id not in self.movie_to_idx:
            return 0.0
        return self._predict_idx(self.user_to_idx[user_id], self.movie_to_idx[movie_id])

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        if self.matrix is None or user_id not in self.user_to_idx:
            return []
        seen = self.seen_by_user.get(user_id, set()) if exclude_seen else set()
        uidx = self.user_to_idx[user_id]
        candidates: list[tuple[int, float]] = []
        for mid, midx in self.movie_to_idx.items():
            if mid in seen:
                continue
            pred = self._predict_idx(uidx, midx)
            if pred > 0:
                candidates.append((mid, pred))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [
            self._format_movie(mid, score, "与你口味相似的用户喜欢这部电影")
            for mid, score in candidates[:top_k]
        ]
