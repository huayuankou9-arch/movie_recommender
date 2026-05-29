from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors

from src.models.base import BaseRecommender


class UserCFRecommender(BaseRecommender):
    name = "usercf"

    def __init__(
        self,
        movies_df: pd.DataFrame,
        top_k_neighbors: int = 80,
        shrinkage: float = 10.0,
        min_common_items: int = 2,
    ):
        super().__init__(movies_df)
        self.top_k_neighbors = top_k_neighbors
        self.shrinkage = shrinkage
        self.min_common_items = min_common_items
        self.matrix: csr_matrix | None = None
        self.centered_matrix: csr_matrix | None = None
        self.binary_matrix: csr_matrix | None = None
        self.nn: NearestNeighbors | None = None
        self.user_to_idx: dict[int, int] = {}
        self.idx_to_user: dict[int, int] = {}
        self.movie_to_idx: dict[int, int] = {}
        self.idx_to_movie: dict[int, int] = {}
        self.seen_by_user: dict[int, set[int]] = defaultdict(set)
        self.user_mean: dict[int, float] = {}
        self.movie_mean: dict[int, float] = {}
        self.global_mean = 3.5
        self.popular_fallback: list[int] = []

    def fit(self, train_ratings: pd.DataFrame, matrix_bundle: dict[str, object]) -> None:
        self.matrix = matrix_bundle["matrix"].tocsr()
        user_encoder = matrix_bundle["user_encoder"]
        movie_encoder = matrix_bundle["movie_encoder"]
        self.user_to_idx = {int(uid): int(i) for i, uid in enumerate(user_encoder.classes_)}
        self.idx_to_user = {v: k for k, v in self.user_to_idx.items()}
        self.movie_to_idx = {int(mid): int(i) for i, mid in enumerate(movie_encoder.classes_)}
        self.idx_to_movie = {v: k for k, v in self.movie_to_idx.items()}
        self.global_mean = float(train_ratings["rating"].mean()) if not train_ratings.empty else 3.5
        self.user_mean = train_ratings.groupby("userId")["rating"].mean().astype(float).to_dict()
        self.movie_mean = train_ratings.groupby("movieId")["rating"].mean().astype(float).to_dict()
        self.popular_fallback = (
            train_ratings.groupby("movieId")["rating"]
            .agg(["mean", "count"])
            .sort_values(["mean", "count"], ascending=False)
            .index.astype(int)
            .tolist()
        )
        for row in train_ratings.itertuples(index=False):
            self.seen_by_user[int(row.userId)].add(int(row.movieId))

        centered = self.matrix.copy().astype(float).tolil()
        for uid, uidx in self.user_to_idx.items():
            start = self.matrix.indptr[uidx]
            end = self.matrix.indptr[uidx + 1]
            if end > start:
                cols = self.matrix.indices[start:end]
                centered[uidx, cols] = self.matrix.data[start:end] - self.user_mean.get(uid, self.global_mean)
        self.centered_matrix = centered.tocsr()
        self.binary_matrix = self.matrix.copy()
        self.binary_matrix.data = np.ones_like(self.binary_matrix.data)

        n_neighbors = min(max(2, self.top_k_neighbors + 1), self.matrix.shape[0])
        self.nn = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=n_neighbors)
        self.nn.fit(self.centered_matrix)

    def _neighbors_for_user(self, uidx: int) -> list[tuple[int, float]]:
        if self.nn is None or self.centered_matrix is None or self.binary_matrix is None:
            return []
        distances, indices = self.nn.kneighbors(self.centered_matrix[uidx], return_distance=True)
        target_seen = set(self.binary_matrix[uidx].indices.tolist())
        out: list[tuple[int, float]] = []
        for dist, vidx in zip(distances[0], indices[0]):
            vidx = int(vidx)
            if vidx == uidx:
                continue
            common = len(target_seen.intersection(self.binary_matrix[vidx].indices.tolist()))
            if common < self.min_common_items:
                continue
            sim = max(0.0, 1.0 - float(dist))
            sim *= common / (common + self.shrinkage)
            if sim > 0:
                out.append((vidx, sim))
        return out[: self.top_k_neighbors]

    def _predict_idx(self, uidx: int, midx: int) -> float:
        if self.matrix is None or self.centered_matrix is None:
            return self.global_mean
        uid = self.idx_to_user.get(uidx)
        base = self.user_mean.get(uid, self.global_mean)
        num = 0.0
        den = 0.0
        for vidx, sim in self._neighbors_for_user(uidx):
            rating = float(self.matrix[vidx, midx])
            if rating <= 0:
                continue
            vid = self.idx_to_user.get(vidx)
            centered = rating - self.user_mean.get(vid, self.global_mean)
            num += sim * centered
            den += abs(sim)
        if den <= 1e-10:
            mid = self.idx_to_movie.get(midx)
            return float(np.clip(self.movie_mean.get(mid, self.global_mean), 0.5, 5.0))
        return float(np.clip(base + num / den, 0.5, 5.0))

    def score(self, user_id: int, movie_id: int) -> float:
        if user_id not in self.user_to_idx or movie_id not in self.movie_to_idx:
            return float(np.clip(self.movie_mean.get(int(movie_id), self.global_mean), 0.5, 5.0))
        return self._predict_idx(self.user_to_idx[user_id], self.movie_to_idx[movie_id])

    def score_items(self, user_id: int, movie_ids: list[int]) -> dict[int, float]:
        if self.matrix is None or user_id not in self.user_to_idx:
            return {int(mid): float(np.clip(self.movie_mean.get(int(mid), self.global_mean), 0.5, 5.0)) for mid in movie_ids}
        uidx = self.user_to_idx[user_id]
        base = self.user_mean.get(user_id, self.global_mean)
        mids = [int(mid) for mid in movie_ids]
        out = {mid: self.movie_mean.get(mid, self.global_mean) for mid in mids}
        mids_in = [mid for mid in mids if mid in self.movie_to_idx]
        if not mids_in:
            return {mid: float(np.clip(v, 0.5, 5.0)) for mid, v in out.items()}
        midx = np.array([self.movie_to_idx[mid] for mid in mids_in], dtype=int)
        num = np.zeros(len(mids_in), dtype=float)
        den = np.zeros(len(mids_in), dtype=float)
        for vidx, sim in self._neighbors_for_user(uidx):
            vals = self.matrix[vidx, midx].toarray().ravel()
            mask = vals > 0
            if not mask.any():
                continue
            vid = self.idx_to_user.get(vidx)
            centered = vals[mask] - self.user_mean.get(vid, self.global_mean)
            num[mask] += sim * centered
            den[mask] += abs(sim)
        pred = np.where(den > 1e-10, base + num / np.maximum(den, 1e-10), [out[mid] for mid in mids_in])
        pred = np.clip(pred, 0.5, 5.0)
        for mid, val in zip(mids_in, pred):
            out[mid] = float(val)
        return {mid: float(np.clip(out[mid], 0.5, 5.0)) for mid in mids}

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        if self.matrix is None or user_id not in self.user_to_idx:
            return self._fallback(user_id, top_k, exclude_seen)
        seen = self.seen_by_user.get(user_id, set()) if exclude_seen else set()
        uidx = self.user_to_idx[user_id]
        candidates: set[int] = set()
        for vidx, sim in self._neighbors_for_user(uidx):
            start = self.matrix.indptr[vidx]
            end = self.matrix.indptr[vidx + 1]
            for midx in self.matrix.indices[start:end]:
                mid = self.idx_to_movie[int(midx)]
                if mid in seen:
                    continue
                candidates.add(mid)
        score_map = self.score_items(user_id, list(candidates))
        ranked = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        out = [
            self._format_movie(
                mid,
                score,
                "Users with similar taste also rated this movie highly",
                reason_type="usercf",
                evidence="Cosine-nearest neighbors with mean-centered ratings support this recommendation.",
                score_breakdown={"usercf": score},
            )
            for mid, score in ranked[:top_k]
        ]
        if len(out) < top_k:
            used = {int(x["movieId"]) for x in out}
            out.extend(self._fallback(user_id, top_k - len(out), exclude_seen, used))
        return out[:top_k]

    def _fallback(self, user_id: int, top_k: int, exclude_seen: bool = True, used: set[int] | None = None) -> list[dict]:
        seen = self.seen_by_user.get(user_id, set()) if exclude_seen else set()
        used = used or set()
        out = []
        for mid in self.popular_fallback:
            if mid in seen or mid in used:
                continue
            score = self.movie_mean.get(mid, self.global_mean)
            out.append(
                self._format_movie(
                    mid,
                    score,
                    "Fallback from highly rated popular movies when user-neighbor evidence is sparse",
                    reason_type="usercf_fallback",
                    evidence="UserCF fallback keeps the recommendation list non-empty without using test data.",
                    score_breakdown={"usercf": score},
                )
            )
            if len(out) >= top_k:
                break
        return out
