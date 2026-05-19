from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from src.models.base import BaseRecommender


class HybridRecommender(BaseRecommender):
    name = "hybrid"

    def __init__(
        self,
        movies_df: pd.DataFrame,
        popularity_model,
        usercf_model,
        itemcf_model,
        mf_model,
        content_model,
        weights: dict[str, float],
    ):
        super().__init__(movies_df)
        self.popularity_model = popularity_model
        self.usercf_model = usercf_model
        self.itemcf_model = itemcf_model
        self.mf_model = mf_model
        self.content_model = content_model
        self.weights = weights

    def fit(self, *args, **kwargs) -> None:
        return None

    @staticmethod
    def _norm_scores(score_map: dict[int, float]) -> dict[int, float]:
        if not score_map:
            return {}
        vals = np.array(list(score_map.values()), dtype=float)
        vmin = float(vals.min())
        vmax = float(vals.max())
        if abs(vmax - vmin) < 1e-8:
            return {k: 0.5 for k in score_map.keys()}
        return {k: float((v - vmin) / (vmax - vmin)) for k, v in score_map.items()}

    def _recall_candidates(self, user_id: int, each_top: int = 100) -> dict[str, dict[int, float]]:
        model_outputs = {
            "popularity": self.popularity_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "usercf": self.usercf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "itemcf": self.itemcf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "mf": self.mf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "content": self.content_model.recommend(user_id, top_k=each_top, exclude_seen=True),
        }
        out: dict[str, dict[int, float]] = {}
        for name, recs in model_outputs.items():
            out[name] = {int(r["movieId"]): float(r["score"]) for r in recs}
        return out

    def score(self, user_id: int, movie_id: int) -> float:
        w = self.weights
        return (
            w["popularity"] * self.popularity_model.score(user_id, movie_id)
            + w["usercf"] * self.usercf_model.score(user_id, movie_id)
            + w["itemcf"] * self.itemcf_model.score(user_id, movie_id)
            + w["mf"] * self.mf_model.score(user_id, movie_id)
            + w["content"] * self.content_model.score(user_id, movie_id)
        )

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        recalls = self._recall_candidates(user_id, each_top=100)
        all_movie_ids = set()
        for mp in recalls.values():
            all_movie_ids.update(mp.keys())

        normed = {name: self._norm_scores(score_map) for name, score_map in recalls.items()}
        combined: list[tuple[int, float, list[str]]] = []
        for mid in all_movie_ids:
            parts = {
                "popularity": normed["popularity"].get(mid, 0.0),
                "usercf": normed["usercf"].get(mid, 0.0),
                "itemcf": normed["itemcf"].get(mid, 0.0),
                "mf": normed["mf"].get(mid, 0.0),
                "content": normed["content"].get(mid, 0.0),
            }
            score = sum(self.weights[k] * parts[k] for k in parts)
            reasons = [k for k, v in parts.items() if v > 0.01]
            combined.append((mid, float(score), reasons))

        combined.sort(key=lambda x: x[1], reverse=True)
        out = []
        for mid, score, reasons in combined[:top_k]:
            if {"itemcf", "usercf", "content"}.issubset(set(reasons)):
                reason = "因为你喜欢相似电影，且相似用户也喜欢这部电影"
            elif len(reasons) >= 3:
                reason = "综合相似用户、相似电影和内容特征推荐"
            else:
                reason = "多模型综合推荐"
            out.append(self._format_movie(mid, score, reason))
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        scores: dict[int, float] = defaultdict(float)
        for rec in self.itemcf_model.similar_movies(movie_id, top_k=top_k * 2):
            scores[int(rec["movieId"])] += 0.6 * float(rec["score"])
        for rec in self.content_model.similar_movies(movie_id, top_k=top_k * 2):
            scores[int(rec["movieId"])] += 0.4 * float(rec["score"])
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [self._format_movie(mid, s, "综合协同过滤与内容特征的相似推荐") for mid, s in ranked]
