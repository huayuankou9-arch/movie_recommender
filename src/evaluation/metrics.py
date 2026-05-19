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


def precision_recall_hit_ndcg_at_k(
    recs: list[int], positives: set[int], k: int
) -> tuple[float, float, float, float]:
    if k <= 0:
        return 0.0, 0.0, 0.0, 0.0
    topk = recs[:k]
    hits = [1 if m in positives else 0 for m in topk]
    hit_count = sum(hits)
    precision = hit_count / k
    recall = hit_count / len(positives) if positives else 0.0
    hitrate = 1.0 if hit_count > 0 else 0.0
    dcg = 0.0
    for i, h in enumerate(hits, start=1):
        if h:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(positives), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg > 0 else 0.0
    return float(precision), float(recall), float(hitrate), float(ndcg)
