from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def rmse(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_t = np.array(list(y_true), dtype=float)
    y_p = np.array(list(y_pred), dtype=float)
    if len(y_t) == 0:
        return 0.0
    return float(np.sqrt(np.mean((y_t - y_p) ** 2)))


def mae(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_t = np.array(list(y_true), dtype=float)
    y_p = np.array(list(y_pred), dtype=float)
    if len(y_t) == 0:
        return 0.0
    return float(np.mean(np.abs(y_t - y_p)))


def precision_at_k(recommended: list[int], positives: set[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(recommended[:k]).intersection(positives)) / k


def recall_at_k(recommended: list[int], positives: set[int], k: int) -> float:
    if not positives:
        return 0.0
    return len(set(recommended[:k]).intersection(positives)) / len(positives)


def hit_rate_at_k(recommended: list[int], positives: set[int], k: int) -> float:
    return 1.0 if set(recommended[:k]).intersection(positives) else 0.0


def ndcg_at_k(recommended: list[int], positives: set[int], k: int) -> float:
    if k <= 0 or not positives:
        return 0.0
    topk = recommended[:k]
    dcg = 0.0
    for i, movie_id in enumerate(topk):
        if movie_id in positives:
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(len(positives), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return float(dcg / idcg) if idcg > 0 else 0.0


def coverage(all_recommendations: Iterable[int], all_items: set[int]) -> float:
    if not all_items:
        return 0.0
    return len(set(all_recommendations)) / len(all_items)


def precision_recall_hit_ndcg_at_k(recs: list[int], positives: set[int], k: int) -> tuple[float, float, float, float]:
    return (
        precision_at_k(recs, positives, k),
        recall_at_k(recs, positives, k),
        hit_rate_at_k(recs, positives, k),
        ndcg_at_k(recs, positives, k),
    )
