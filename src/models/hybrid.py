from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from src.models.base import BaseRecommender


class HybridRecommender(BaseRecommender):
    name = "hybrid"

    def __init__(self, movies_df: pd.DataFrame, popularity_model, usercf_model, itemcf_model, mf_model, content_model, weights: dict[str, float], recall_top: int = 200):
        super().__init__(movies_df)
        self.popularity_model = popularity_model
        self.usercf_model = usercf_model
        self.itemcf_model = itemcf_model
        self.mf_model = mf_model
        self.content_model = content_model
        self.weights = self._clean_weights(weights)
        self.recall_top = recall_top

    def fit(self, *args, **kwargs) -> None:
        return None

    @staticmethod
    def _clean_weights(weights: dict[str, float]) -> dict[str, float]:
        base = weights.get("weights", weights.get("default_weights", weights))
        out = {k: float(base.get(k, 0.0)) for k in ["popularity", "usercf", "itemcf", "mf", "content"]}
        total = sum(out.values()) or 1.0
        return {k: v / total for k, v in out.items()}

    def set_weights(self, weights: dict[str, float]) -> None:
        self.weights = self._clean_weights(weights)

    @staticmethod
    def _norm_scores(score_map: dict[int, float]) -> dict[int, float]:
        if not score_map:
            return {}
        vals = np.array(list(score_map.values()), dtype=float)
        vmin = float(vals.min())
        vmax = float(vals.max())
        if abs(vmax - vmin) < 1e-12:
            return {k: 0.5 for k in score_map.keys()}
        return {k: float((v - vmin) / (vmax - vmin + 1e-12)) for k, v in score_map.items()}

    def _recall_candidates(self, user_id: int, each_top: int | None = None) -> tuple[dict[str, dict[int, float]], dict[int, dict]]:
        each_top = each_top or self.recall_top
        outputs = {
            "popularity": self.popularity_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "usercf": self.usercf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "itemcf": self.itemcf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "mf": self.mf_model.recommend(user_id, top_k=each_top, exclude_seen=True),
            "content": self.content_model.recommend(user_id, top_k=each_top, exclude_seen=True),
        }
        score_maps: dict[str, dict[int, float]] = {}
        payloads: dict[int, dict] = {}
        for name, recs in outputs.items():
            score_maps[name] = {}
            for rec in recs or []:
                mid = int(rec["movieId"])
                score_maps[name][mid] = float(rec.get("score", 0.0))
                payloads.setdefault(mid, rec)
        return score_maps, payloads

    def score_breakdown_for(self, user_id: int, movie_id: int) -> dict[str, float]:
        raw = {
            "popularity": float(self.popularity_model.score(user_id, movie_id)),
            "usercf": float(self.usercf_model.score(user_id, movie_id)),
            "itemcf": float(self.itemcf_model.score(user_id, movie_id)),
            "mf": float(self.mf_model.score(user_id, movie_id)),
            "content": float(self.content_model.score(user_id, movie_id)),
        }
        # For point-wise scoring we map rating-scale models roughly to 0-1 and leave bounded signals as-is.
        norm = {
            "popularity": np.clip(raw["popularity"], 0, 1),
            "usercf": np.clip((raw["usercf"] - 0.5) / 4.5, 0, 1),
            "itemcf": np.clip((raw["itemcf"] - 0.5) / 4.5, 0, 1),
            "mf": np.clip((raw["mf"] - 0.5) / 4.5, 0, 1),
            "content": np.clip(raw["content"], 0, 1),
        }
        hybrid = sum(self.weights[k] * norm[k] for k in self.weights)
        return {**raw, "hybrid": float(hybrid)}

    def score(self, user_id: int, movie_id: int) -> float:
        return self.score_breakdown_for(user_id, movie_id)["hybrid"]

    def score_items(self, user_id: int, movie_ids: list[int]) -> dict[int, float]:
        mids = [int(mid) for mid in movie_ids]
        raw_maps = {
            "popularity": self.popularity_model.score_items(user_id, mids) if hasattr(self.popularity_model, "score_items") else {mid: self.popularity_model.score(user_id, mid) for mid in mids},
            "usercf": self.usercf_model.score_items(user_id, mids) if hasattr(self.usercf_model, "score_items") else {mid: self.usercf_model.score(user_id, mid) for mid in mids},
            "itemcf": self.itemcf_model.score_items(user_id, mids) if hasattr(self.itemcf_model, "score_items") else {mid: self.itemcf_model.score(user_id, mid) for mid in mids},
            "mf": self.mf_model.score_items(user_id, mids) if hasattr(self.mf_model, "score_items") else {mid: self.mf_model.score(user_id, mid) for mid in mids},
            "content": self.content_model.score_items(user_id, mids) if hasattr(self.content_model, "score_items") else {mid: self.content_model.score(user_id, mid) for mid in mids},
        }
        normed = {name: self._norm_scores(score_map) for name, score_map in raw_maps.items()}
        return {
            mid: float(sum(self.weights[k] * normed.get(k, {}).get(mid, 0.0) for k in self.weights))
            for mid in mids
        }

    def _reason_from_parts(self, mid: int, parts: dict[str, float], payload: dict | None) -> tuple[str, str, str | list[str], dict | None]:
        winner = max(parts.items(), key=lambda x: x[1])[0] if parts else "hybrid"
        source = payload.get("source_movie") if isinstance(payload, dict) else None
        if winner == "itemcf":
            title = source.get("title") if isinstance(source, dict) else "a movie you liked"
            return f"Because you liked {title}", "hybrid_itemcf", [title, "strong item-neighborhood contribution"], source
        if winner == "mf":
            return "Predicted as a strong match for your taste", "hybrid_mf", "Latent factor prediction is the largest contributor.", None
        if winner == "content":
            return "Similar genres, tags, and story elements", "hybrid_content", "Content profile contributes most to the hybrid score.", None
        if winner == "popularity":
            return "Highly rated and widely watched", "hybrid_popularity", "Popularity is the strongest normalized signal.", None
        if winner == "usercf":
            return "Users with similar taste also liked this movie", "hybrid_usercf", "User-neighbor evidence is the strongest normalized signal.", None
        return "Best blended match across multiple recommenders", "hybrid", "Multiple recommenders agree on this item.", None

    def recommend(self, user_id: int, top_k: int = 12, exclude_seen: bool = True) -> list[dict]:
        recalls, payloads = self._recall_candidates(user_id, each_top=self.recall_top)
        all_movie_ids: set[int] = set()
        for mp in recalls.values():
            all_movie_ids.update(mp.keys())
        normed = {name: self._norm_scores(score_map) for name, score_map in recalls.items()}
        combined: list[tuple[int, float, dict[str, float], dict[str, float]]] = []
        for mid in all_movie_ids:
            parts = {name: normed.get(name, {}).get(mid, 0.0) for name in ["popularity", "usercf", "itemcf", "mf", "content"]}
            raw = {name: recalls.get(name, {}).get(mid, 0.0) for name in parts}
            score = sum(self.weights[k] * parts[k] for k in parts)
            combined.append((mid, float(score), parts, raw))
        combined.sort(key=lambda x: x[1], reverse=True)
        out = []
        for mid, score, parts, raw in combined[:top_k]:
            reason, reason_type, evidence, source = self._reason_from_parts(mid, parts, payloads.get(mid))
            out.append(
                self._format_movie(
                    mid,
                    score,
                    reason,
                    reason_type=reason_type,
                    evidence=evidence,
                    score_breakdown={**raw, "hybrid": score},
                    source_movie=source,
                )
            )
        return out

    def similar_movies(self, movie_id: int, top_k: int = 12) -> list[dict]:
        scores: dict[int, float] = defaultdict(float)
        for rec in self.itemcf_model.similar_movies(movie_id, top_k=top_k * 3):
            scores[int(rec["movieId"])] += 0.6 * float(rec.get("score", 0.0))
        for rec in self.content_model.similar_movies(movie_id, top_k=top_k * 3):
            scores[int(rec["movieId"])] += 0.4 * float(rec.get("score", 0.0))
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [self._format_movie(mid, s, "Hybrid similar movie from collaborative and content evidence", reason_type="hybrid", score_breakdown={"hybrid": s}) for mid, s in ranked]
