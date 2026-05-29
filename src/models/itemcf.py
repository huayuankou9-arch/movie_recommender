from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors

from src.models.base import BaseRecommender


class ItemCFRecommender(BaseRecommender):
    name = "itemcf"

    def __init__(
        self,
        movies_df: pd.DataFrame,
        top_n_similar: int = 100,
        positive_threshold: float = 4.0,
        use_positive_history_only: bool = True,
        normalize_scores: bool = True,
    ):
        super().__init__(movies_df)
        self.top_n_similar = top_n_similar
        self.positive_threshold = positive_threshold
        self.use_positive_history_only = use_positive_history_only
        self.normalize_scores = normalize_scores
        self.matrix: csr_matrix | None = None
        self.user_to_idx: dict[int, int] = {}
        self.idx_to_user: dict[int, int] = {}
        self.movie_to_idx: dict[int, int] = {}
        self.idx_to_movie: dict[int, int] = {}
        self.neighbors: dict[int, list[tuple[int, float]]] = defaultdict(list)
        self.user_rated: dict[int, dict[int, float]] = defaultdict(dict)
        self.user_mean: dict[int, float] = {}
        self.global_mean = 3.5
        self.movie_mean: dict[int, float] = {}

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

    def _source_payload(self, movie_id: int) -> dict:
        meta = self.movie_meta.get(movie_id, {})
        return {
            "movieId": int(movie_id),
            "title": meta.get("title", ""),
            "year": int(meta["year"]) if pd.notna(meta.get("year")) else None,
            "genres": meta.get("genres", ""),
            "poster_url": meta.get("poster_url", ""),
        }

    def _score_with_source(self, user_id: int, movie_id: int) -> tuple[float, int | None, list[str]]:
        rated = self.user_rated.get(user_id, {})
        if not rated:
            return self.movie_mean.get(movie_id, self.global_mean), None, []
        seeds = {mid: r for mid, r in rated.items() if r >= self.positive_threshold}
        if not seeds or not self.use_positive_history_only:
            seeds = rated if not seeds else seeds
        user_mean = self.user_mean.get(user_id, self.global_mean)
        num = 0.0
        den = 0.0
        best_src = None
        best_contrib = -1.0
        for src_mid, src_rating in seeds.items():
            for nb_mid, sim in self.neighbors.get(src_mid, []):
                if nb_mid != movie_id:
                    continue
                val = (src_rating - user_mean) if self.normalize_scores else src_rating
                contrib = sim * val
                num += contrib
                den += abs(sim)
                if abs(contrib) > best_contrib:
                    best_contrib = abs(contrib)
                    best_src = src_mid
        if den <= 1e-10:
            return self.movie_mean.get(movie_id, self.global_mean), best_src, []
        score = user_mean + num / den if self.normalize_scores else num / den
        score = float(np.clip(score, 0.5, 5.0))
        matched = []
        if best_src is not None:
            a = set(str(self.movie_meta.get(best_src, {}).get("genres", "")).split(", "))
            b = set(str(self.movie_meta.get(movie_id, {}).get("genres", "")).split(", "))
            matched = sorted(x for x in a.intersection(b) if x)
        return score, best_src, matched

    def score(self, user_id: int, movie_id: int) -> float:
        score, _, _ = self._score_with_source(user_id, movie_id)
        return float(score)

    def score_items(self, user_id: int, movie_ids: list[int]) -> dict[int, float]:
        return {int(mid): float(self.score(user_id, int(mid))) for mid in movie_ids}

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        rated = self.user_rated.get(user_id, {})
        if not rated:
            return []
        seen = set(rated.keys()) if exclude_seen else set()
        seeds = {mid: r for mid, r in rated.items() if r >= self.positive_threshold}
        if not seeds:
            seeds = rated
        candidate_sources: dict[int, tuple[int, float]] = {}
        for src_mid, src_rating in seeds.items():
            for nb_mid, sim in self.neighbors.get(src_mid, []):
                if nb_mid in seen:
                    continue
                contrib = sim * max(src_rating - self.user_mean.get(user_id, self.global_mean), 0.1)
                prev = candidate_sources.get(nb_mid)
                if prev is None or contrib > prev[1]:
                    candidate_sources[nb_mid] = (src_mid, contrib)
        scored = []
        for mid in candidate_sources:
            s, src_mid, matched = self._score_with_source(user_id, mid)
            scored.append((mid, s, src_mid, matched))
        scored.sort(key=lambda x: x[1], reverse=True)
        out: list[dict] = []
        for mid, s, src_mid, matched in scored[:top_k]:
            src_title = self.movie_meta.get(src_mid, {}).get("title", "a movie you rated highly") if src_mid else "a movie you rated highly"
            out.append(
                self._format_movie(
                    mid,
                    s,
                    f"Because you liked {src_title}",
                    reason_type="itemcf",
                    evidence=[src_title, ", ".join(matched) if matched else "collaborative item similarity"],
                    score_breakdown={"itemcf": s},
                    source_movie=self._source_payload(src_mid) if src_mid else None,
                )
            )
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        sims = self.neighbors.get(movie_id, [])[:top_k]
        src_title = self.movie_meta.get(movie_id, {}).get("title", "this movie")
        return [
            self._format_movie(
                mid,
                sim,
                f"Collaborative neighbors of {src_title}",
                reason_type="itemcf",
                evidence=[src_title, "similar user rating behavior"],
                score_breakdown={"itemcf": sim},
                source_movie=self._source_payload(movie_id),
            )
            for mid, sim in sims
        ]
