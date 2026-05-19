from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from src.models.base import BaseRecommender

try:
    from surprise import Dataset, Reader, SVD  # type: ignore

    HAS_SURPRISE = True
except Exception:
    HAS_SURPRISE = False


class MatrixFactorizationRecommender(BaseRecommender):
    name = "mf"

    def __init__(self, movies_df: pd.DataFrame, n_factors: int = 50, n_epochs: int = 30):
        super().__init__(movies_df)
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.global_mean = 0.0
        self.user_bias: np.ndarray | None = None
        self.item_bias: np.ndarray | None = None
        self.user_factors: np.ndarray | None = None
        self.item_factors: np.ndarray | None = None
        self.user_to_idx: dict[int, int] = {}
        self.idx_to_user: dict[int, int] = {}
        self.movie_to_idx: dict[int, int] = {}
        self.idx_to_movie: dict[int, int] = {}
        self.user_rated: dict[int, set[int]] = defaultdict(set)
        self.rmse_train = None
        self.mae_train = None
        self.use_surprise = False
        self.surprise_model = None

    def fit(self, train_ratings: pd.DataFrame, matrix_bundle: dict[str, object]) -> None:
        user_encoder = matrix_bundle["user_encoder"]
        movie_encoder = matrix_bundle["movie_encoder"]
        self.user_to_idx = {int(uid): int(i) for i, uid in enumerate(user_encoder.classes_)}
        self.idx_to_user = {v: k for k, v in self.user_to_idx.items()}
        self.movie_to_idx = {int(mid): int(i) for i, mid in enumerate(movie_encoder.classes_)}
        self.idx_to_movie = {v: k for k, v in self.movie_to_idx.items()}
        for row in train_ratings.itertuples(index=False):
            self.user_rated[int(row.userId)].add(int(row.movieId))

        if HAS_SURPRISE:
            self._fit_surprise(train_ratings)
        else:
            self._fit_sgd(train_ratings)

    def _fit_surprise(self, train_ratings: pd.DataFrame) -> None:
        reader = Reader(rating_scale=(0.5, 5.0))
        data = Dataset.load_from_df(train_ratings[["userId", "movieId", "rating"]], reader)
        trainset = data.build_full_trainset()
        algo = SVD(n_factors=self.n_factors, n_epochs=self.n_epochs, verbose=False)
        algo.fit(trainset)
        self.surprise_model = algo
        self.use_surprise = True

        preds = []
        trues = []
        for row in train_ratings.itertuples(index=False):
            pred = algo.predict(uid=row.userId, iid=row.movieId).est
            preds.append(pred)
            trues.append(row.rating)
        preds_arr = np.array(preds)
        trues_arr = np.array(trues)
        self.rmse_train = float(np.sqrt(np.mean((preds_arr - trues_arr) ** 2)))
        self.mae_train = float(np.mean(np.abs(preds_arr - trues_arr)))

    def _fit_sgd(self, train_ratings: pd.DataFrame) -> None:
        n_users = len(self.user_to_idx)
        n_items = len(self.movie_to_idx)
        self.global_mean = float(train_ratings["rating"].mean())
        self.user_bias = np.zeros(n_users)
        self.item_bias = np.zeros(n_items)
        self.user_factors = np.random.normal(0, 0.1, size=(n_users, self.n_factors))
        self.item_factors = np.random.normal(0, 0.1, size=(n_items, self.n_factors))

        lr = 0.01
        reg = 0.05
        rows = train_ratings[["userId", "movieId", "rating"]].copy()
        rows["uidx"] = rows["userId"].map(self.user_to_idx)
        rows["iidx"] = rows["movieId"].map(self.movie_to_idx)
        triples = rows[["uidx", "iidx", "rating"]].dropna().values

        for _ in range(self.n_epochs):
            np.random.shuffle(triples)
            for uidx, iidx, rating in triples:
                u = int(uidx)
                i = int(iidx)
                r = float(rating)
                pred = self.global_mean + self.user_bias[u] + self.item_bias[i] + np.dot(
                    self.user_factors[u], self.item_factors[i]
                )
                err = r - pred
                self.user_bias[u] += lr * (err - reg * self.user_bias[u])
                self.item_bias[i] += lr * (err - reg * self.item_bias[i])
                pu = self.user_factors[u].copy()
                qi = self.item_factors[i].copy()
                self.user_factors[u] += lr * (err * qi - reg * pu)
                self.item_factors[i] += lr * (err * pu - reg * qi)

        preds = np.array([self._predict_idx(int(u), int(i)) for u, i, _ in triples])
        trues = np.array([float(r) for _, _, r in triples])
        self.rmse_train = float(np.sqrt(np.mean((preds - trues) ** 2)))
        self.mae_train = float(np.mean(np.abs(preds - trues)))

    def _predict_idx(self, uidx: int, iidx: int) -> float:
        if self.user_factors is None or self.item_factors is None or self.user_bias is None or self.item_bias is None:
            return self.global_mean
        return float(
            self.global_mean
            + self.user_bias[uidx]
            + self.item_bias[iidx]
            + np.dot(self.user_factors[uidx], self.item_factors[iidx])
        )

    def score(self, user_id: int, movie_id: int) -> float:
        if self.use_surprise and self.surprise_model is not None:
            return float(self.surprise_model.predict(uid=user_id, iid=movie_id).est)
        if user_id not in self.user_to_idx or movie_id not in self.movie_to_idx:
            return 0.0
        return self._predict_idx(self.user_to_idx[user_id], self.movie_to_idx[movie_id])

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        seen = self.user_rated.get(user_id, set()) if exclude_seen else set()
        candidates: list[tuple[int, float]] = []
        for mid in self.movie_to_idx.keys():
            if mid in seen:
                continue
            pred = self.score(user_id, mid)
            if pred > 0:
                candidates.append((mid, pred))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [
            self._format_movie(mid, s, "模型预测你可能给出较高评分")
            for mid, s in candidates[:top_k]
        ]

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        if movie_id not in self.movie_to_idx or self.item_factors is None:
            return []
        iidx = self.movie_to_idx[movie_id]
        sims = cosine_similarity(self.item_factors[iidx : iidx + 1], self.item_factors).ravel()
        order = np.argsort(-sims)
        out = []
        for idx in order:
            mid = self.idx_to_movie.get(int(idx))
            if mid is None or mid == movie_id:
                continue
            out.append(self._format_movie(mid, float(sims[idx]), "在潜在兴趣向量空间中相似"))
            if len(out) >= top_k:
                break
        return out
